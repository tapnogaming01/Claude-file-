# Episode Bot (Pyrogram + MongoDB + Render + Deep-Link Batch Delivery)

## Folder structure

```
episode_bot/
├── main.py                # entry point, starts Pyrogram + Render health-check server
├── config.py                # reads all environment variables
├── database.py               # MongoDB (motor/async) helper functions
├── log_utils.py              # sends notifications to the log channel
├── episode_parser.py         # reads captions like "Episode 1-5" / "Episode 3"
├── keyboard.py                # builds the deep-link batch buttons
├── utils.py                    # slugify() — turns a story name into a safe key/payload
├── plugins/
│   ├── start.py                # /start command + deep-link batch delivery
│   ├── admin.py                # /addsource, /removesource, /listsources, /addlogchannel
│   └── source_listener.py      # watches source channels, buffers files, posts batch blocks
├── requirements.txt
├── Procfile
└── .env.example
```

Pyrogram auto-loads every handler inside `plugins/` — no manual imports needed.

## Yeh bot kaise kaam karta hai

1. Aap **source channel** me file (video/document) daalte ho, caption me episode number ke saath
   (jaise `Episode 211` ya `Episode 211-215` agar ek file me combined episodes hain)
2. Bot har file ko **buffer** karta hai. Jab buffer me **5 nayi files** (`FILES_PER_BLOCK`) jama ho jaati
   hain, bot un episodes ko **10-10 ke groups** (`BATCH_SIZE`) me baant kar **target channel par ek naya
   message** post karta hai — har group ka apna button, jaise `211-220`, `221-230`
3. Yeh buttons **normal callback nahi hain — deep links hain**:
   `https://t.me/YourBot?start=batch-<story>-<start>-<end>`
   User jab tap karta hai, Telegram seedha bot ki DM khol deta hai aur `/start batch-...` command bhej
   deta hai
4. Bot us poore batch (jaise episodes 211 se 220 tak) ki **saari files ek saath DM me bhej deta hai**
5. **Log channel** me har file receive hone, naya batch-block post hone, aur har delivery ki notification
   jaati hai

> **Important**: `BOT_USERNAME` env var zaroor set karein (bina `@` ke) — deep-link buttons isi se banate
> hain. Agar galat/khaali hua to buttons kaam nahi karenge.

> **Assumption**: agar ek hi file me kai episodes combined hain, saare us file ke andar hi hain — bot
> unhe alag-alag kaat nahi sakta, sirf ek hi file sabke liye bhej dega.

---

## Environment variables (`.env.example` dekhen)

| Variable | Kya hai |
|---|---|
| `API_ID`, `API_HASH` | https://my.telegram.org se milenge |
| `BOT_TOKEN` | BotFather se milega |
| `BOT_USERNAME` | Bot ka @username bina `@` ke — deep links banane ke liye zaroori |
| `MONGO_URI` | MongoDB Atlas ka connection string (ya self-hosted MongoDB URI) |
| `MONGO_DB_NAME` | Database ka naam (default: `episode_bot`) |
| `ADMIN_IDS` | Jo Telegram user IDs admin commands use kar sakte hain, comma se separate |
| `BATCH_SIZE` | Ek button me kitne episodes (default: `10`) |
| `FILES_PER_BLOCK` | Kitni nayi files par naya block post ho (default: `5`) |
| `PORT` | Render khud set kar deta hai |

---

## Render par deploy kaise karein

1. Is folder ko GitHub repo me push karo
2. Render dashboard → **New → Web Service**
3. Repo connect karo
4. **Build Command**: `pip install -r requirements.txt`
5. **Start Command**: `python main.py`
6. Environment tab me sab variables daal do (`.env.example` dekh ke, `BOT_USERNAME` bhoolna mat)
7. Deploy — Render khud `PORT` set karega, Flask health-check usi par chalega

---

## Bot commands (sirf `ADMIN_IDS` wale, private chat me)

```
/addsource <source_channel_id> <story_name> <target_channel_id>
/removesource <source_channel_id>
/listsources
/addlogchannel <log_channel_id>
```

Example:
```
/addsource -1001111111111 MyMysteriousHusband -1002222222222
/addlogchannel -1003333333333
```

**Zaroori**: Bot ko source, target, aur log — teeno channels me **admin** banana hoga.

---

## Local test karne ke liye

```bash
pip install -r requirements.txt
cp .env.example .env   # values fill karo, phir export karo ya python-dotenv use karo
python main.py
```

---

## Abhi jo clear nahi hai / aage decide karna hoga

- Maths wala feature (jo sabse pehle mention hua tha) — abhi is bot me include nahi kiya
- Har batch-block ki caption me "Tutorial / Help Us / Support / Buy This Story" jaise extra buttons
  (screenshot me the) — abhi include nahi kiye, chahiye to bata dena
- Kya episode-range hamesha naye story ke start se fixed multiples of 10 honi chahiye (e.g. hamesha
  1-10, 11-20...), ya jo bhi us waqt buffer me episodes hain unko hi 10-10 me chunk kar dena (abhi yehi
  ho raha hai) — agar pehla wala chahiye to bata dena, thoda alag logic lagega
