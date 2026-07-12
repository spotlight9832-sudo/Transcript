# Transcript Telegram Bot (YouTube + RedNote)

Video ka link bhejo → bot transcript text mein, clean chunks mein bhej dega.
- **YouTube**: caption languages dikhayega, jo chuno wahi bhej dega (instant).
- **RedNote / Xiaohongshu**: audio download karke free local speech-to-text
  se transcript banata hai (slower, aur download kabhi kabhi fail ho sakta
  hai — neeche wajah likhi hai).

## Project structure

```
bot.py                       # Telegram handlers + routing (YouTube vs RedNote)
chunking.py                  # shared 3000-word / word-safe chunk splitter
sources/
  youtube_source.py          # YouTube caption API
  rednote_source.py          # RedNote audio download (yt-dlp)
transcription/
  backends.py                # pluggable speech-to-text (local_whisper today)
```

## Setup

1. **Bot token lo**: Telegram par [@BotFather](https://t.me/BotFather) ko
   `/newbot` bhejo, jo token mile use copy kar lo.

2. **ffmpeg install karo** (RedNote audio-extraction ke liye chahiye):
   ```bash
   sudo apt install ffmpeg      # VPS / Debian / Ubuntu
   pkg install ffmpeg           # Termux
   ```

3. **Install karo** (Python 3.10+ chahiye):
   ```bash
   pip install -r requirements.txt
   ```

4. **`.env` banao** (`.env.example` ko copy karke):
   ```bash
   cp .env.example .env
   ```
   Usme apna `BOT_TOKEN` daal do.

5. **Run karo**:
   ```bash
   python bot.py
   ```

## YouTube VPS IP-block ka jugaad

YouTube ab AWS/GCP/Azure/DigitalOcean jaise cloud providers ke IP ranges ko
block kar deta hai — is bot ke andar `RequestBlocked` / `IpBlocked` error
isi wajah se aayega. Do raaste hain, ek free aur ek paid:

### Option A — Free: VPS chodo, residential IP se hi run karo

Blocking sirf **cloud/datacenter IP ranges** par lagti hai — tumhare ghar ka
internet ya phone ka mobile data isme kabhi included nahi tha. To sabse
seedha free fix: isi `bot.py` ko VPS ki jagah kisi residential connection
se chalao. Code mein koi change nahi chahiye — `.env` mein `WEBSHARE_*`
fields khaali chhod do, bot automatically bina proxy ke chalega.

Options (jo bhi available ho):
- Ghar ka koi purana laptop/PC jo 24/7 on rakh sako.
- **Termux (Android)** — tum already Termux use kar chuke ho, to same steps:
  `pkg install python`, phir `pip install -r requirements.txt`, phir
  `python bot.py`. Battery optimization Termux ke liye off kar dena aur
  `termux-wake-lock` chala dena taaki background mein na ruke.
- Ek sasta **Raspberry Pi** (~₹3000-4000 one-time) — isko ek baar setup
  karke chhod do, bijli ke alawa koi running cost nahi.

Mobile data (WiFi nahi) se Termux chalane par bhi generally chal jata hai,
kyunki carrier IPs bhi us "cloud provider" wali blocked category mein nahi
aate.

### Option B — Paid: Webshare Residential proxy (agar VPS par hi rakhna hai)

⚠️ Webshare ka **free tier sirf datacenter proxies** deta hai (10 free
proxies, 1GB) — wahi category jo already block ho rahi hai, to ye specific
problem isse solve nahi hoga. Residential proxy hamesha paid hi hai (kisi
bhi provider ka), kyunki wo real logon ke ghar ke IP use karta hai jiska
cost lagta hai. Agar VPS par hi rakhna zaroori hai:

1. [Webshare](https://www.webshare.io) par account banao.
2. **"Residential"** proxy package lo. ⚠️ "Proxy Server" ya "Static
   Residential" mat lena — sirf rotating residential reliably kaam karta hai.
3. [Proxy Settings](https://dashboard.webshare.io/proxy/settings) se
   "Proxy Username" aur "Proxy Password" copy karke `.env` mein daal do.

Ye do values `.env` mein set hote hi bot automatically saare YouTube
requests us proxy se route karega.

## RedNote (Xiaohongshu) support

RedNote mein YouTube jaisa koi text-caption API nahi hai, isliye pipeline
alag hai: `yt-dlp` se post ka audio download hota hai, phir usse
**faster-whisper** (free, local speech-to-text) se transcribe kiya jata hai.
Isliye ye YouTube se dheema hoga, aur pehli baar chalane par model download
(~150MB "base" size ke liye) bhi hoga.

Supported link formats: `xiaohongshu.com/...`, `xhslink.com/o/...` (short
links), aur `rednote.com/...` (site ka naya domain).

### Backend badalna (jaisa tumne bola tha)

`transcription/backends.py` mein ek `TranscriptionBackend` abstract class
hai. Abhi sirf `LocalWhisperBackend` (free) implement hai, `.env` mein
`TRANSCRIPTION_BACKEND=local_whisper` set hai by default. Kal ko paid API
lagani ho (jaise fast ho ya accuracy chahiye) to bas:
1. `backends.py` mein ek naya class likho (`.transcribe(audio_path)` method
   ke saath, jaisa `LocalWhisperBackend` mein hai).
2. `get_transcription_backend()` mein ek `elif` branch add karo.
3. `.env` mein `TRANSCRIPTION_BACKEND` badal do.

Bot ka baaki code — download, chunking, sending — bilkul touch nahi karna
padega.

### ⚠️ Known limitations (important, padh lena)

- **RedNote CAPTCHA**: RedNote ne recently automated downloads par CAPTCHA
  tighten kiya hai jo yt-dlp ke apne bug tracker ke mutabik "easily bypass
  nahi hota". Matlab **kuch links download hote waqt fail ho sakte hain** —
  ye is bot ka bug nahi, RedNote ki taraf se active blocking hai. Agar fail
  ho: `pip install -U yt-dlp` karke retry karo (fixes wahan land hote hain),
  thodi der baad try karo, ya doosra post try karo.
- RedNote ne domain bhi xiaohongshu.com se **rednote.com** pe shift kiya hai
  recently — yt-dlp ka extractor kabhi kabhi isi wajah se peeche reh jata
  hai jab tak update nahi aata.
- **Native captions kabhi milen bhi to guarantee nahi** — kuch posts mein
  creator-added captions hoti hain, lekin koi reliable API nahi hai unhe
  alag se fetch karne ka, isliye bot hamesha speech-to-text hi karta hai
  (chahe caption already ho).
- **Speech-to-text 100% accurate nahi hota**, khaaskar background music,
  overlapping voices, ya bahut fast speech mein. "base" model se better
  accuracy chahiye to `.env` mein `WHISPER_MODEL_SIZE=small` ya `medium`
  try karo (slower + zyada RAM lagega).

### Maine kya test kiya, kya nahi

Mera sandbox environment mein internet access nahi hai, isliye main khud
`yt-dlp` se koi real RedNote link download nahi kar saka, na hi
`faster-whisper` model load karke asli audio transcribe kar saka — wo dono
network maangte hain jo yahan available nahi hai. Jo maine actually test
kiya (real code par, fake data se nahi):
- Har file syntax-check hui (`py_compile`) — koi typo/syntax error nahi.
- Poora `bot.py` import karke confirm kiya sab modules sahi se wire hain.
- RedNote URL detection tumhare diye hue exact link
  (`http://xhslink.com/o/7vug1bcBgRa`) samet sabhi URL shapes par test kiya.
- Confirm kiya YouTube aur RedNote detectors ek doosre ke links galti se
  pick nahi karte.
- Transcription-backend switching logic (env vars, default, error handling)
  test kiya.

Jo test **nahi** ho paya: asli RedNote se download hona aur asli audio
transcribe hona — pehla real run tumhe hi karna hoga. Agar kuch fail ho to
error message clear hoga (upar wale limitations mein se koi hoga), aur
mujhe bata dena, fix kar denge.

## 3000-word split ka logic

Jo bola tha — 3000 words par split, aur beech mein koi word na tute — wahi
hai, lekin ek cheez clear kar dun: Telegram ka **hard limit 4096 characters
per message** hai, aur real transcript text mein 3000 words almost hamesha
4096 characters se zyada ho jaate hain. Isliye bot dono limits check karta
hai — 3000 words ya ~3900 characters, jo bhi pehle aaye — aur wahi par
split karta hai, **hamesha ek complete word ke baad, kabhi bhi word ke
beech mein nahi.**

Jaise tumne example diya — "...Eren Yeager..." agar split-point ke paas
aaye, to bot "Eren" ke baad hi todega, "Ere" + "n Yeager" jaisa kabhi nahi
karega.

Practically: real transcripts mein character-limit hi zyada tar pehle hit
hota hai, to har part usually ~600-700 words ka aayega (poore 3000 nahi) —
lekin koi word kabhi split nahi hoga. Test karke confirm kiya hai.

## Known limitations

- **Age-restricted videos**: library abhi cookie-login support nahi karti
  (YouTube ne recently ye feature upstream break kar diya tha), to aise
  videos access nahi honge.
- **`PoTokenRequired` error**: kuch specific videos ke liye YouTube extra
  bot-verification maangta hai jo ye library abhi fully solve nahi karti —
  proxy isko fix *nahi* karega, ye library maintainer ke paas open issue
  hai. Doosra video try karna hi filhaal ka solution hai.
- Agar bot restart ho jaye language-list dikhane aur select karne ke beech
  mein, to cache clear ho jayegi — bas video link dobara bhej do.
