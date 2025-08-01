# 🛒 SKT Kontrol Botu

SKT Kontrol Botu, son kullanma tarihi (SKT) yaklaşan ürünleri takip eden ve kullanıcılara zamanında hatırlatma gönderen bir Telegram botudur.

## 🚀 Özellikler

- ✅ Ürün Ekleme – Kullanıcılar ürün adı, SKT ve opsiyonel olarak kategori belirtebilir
- ✅ Listeleme – Kullanıcılar, kayıtlı ürünlerini SKT sırasına göre görüntüleyebilir
- ✅ Otomatik Hatırlatma – SKT'ye 7 gün kalan ürünleri otomatik olarak bildirir
- ✅ Detaylı Ürün Bilgileri – Ürün açıklamaları, eklenme tarihi gibi ek veriler tutulur
- ✅ Ürün Düzenleme & Silme – Kullanıcılar kayıtlı ürünleri güncelleyebilir veya silebilir

## 📌 Gereksinimler

- Python 3.x
- python-telegram-bot
- SQLAlchemy
- APScheduler
- python-dotenv

## 🛠️ Kurulum

1. Gereksinimleri yükleyin:
```bash
pip install -r requirements.txt
```

2. BotFather üzerinden bir Telegram botu oluşturun ve token alın.

3. `.env` dosyasını düzenleyin:
```ini
TELEGRAM_BOT_TOKEN=your_bot_token_here
DATABASE_URL=sqlite:///skt_bot.db
```

4. Veritabanını oluşturun:
```bash
python init_db.py
```

5. Botu çalıştırın:
```bash
python bot.py
```

## 📜 Komutlar

- `/start` - Botu başlatır ve ana menüyü gösterir
- `/urun_ekle` - Yeni bir ürün eklemenizi sağlar
- `/urun_listele` - SKT'ye göre sıralanmış ürün listesini gösterir
- `/urun_sil` - Bir ürünü silmek için kullanılır
- `/duzenle` - Ürün bilgilerini güncellemek için kullanılır
- `/yardim` - Kullanım kılavuzunu gösterir

## 📅 Otomatik Bildirimler

Bot, her gün saat 09:00'da SKT'ye 7 gün kalan ürünler hakkında otomatik bildirim gönderir.

## 🔒 Güvenlik

- `.env` dosyanızı asla paylaşmayın veya sürüm kontrolüne eklemeyin
- Bot token'ınızı gizli tutun
- Hassas verileri şifreleyerek saklayın

## 📝 Lisans

Bu proje MIT lisansı altında lisanslanmıştır.

## Telegram Bot

## Genel Kurulum

1. Repository'yi klonlayın:
```bash
git clone <repository-url>
cd <repository-name>
```

2. Gerekli paketleri yükleyin:
```bash
pip install -r requirements.txt
```

3. `.env` dosyasını oluşturun ve gerekli değişkenleri ekleyin:
```
BOT_TOKEN=your_bot_token
```

4. Botu çalıştırın:
```bash
python bot.py
```

## Termux Üzerinde Kurulum

1. Termux'u yükleyin ve güncelleyin:
```bash
pkg update && pkg upgrade
```

2. Gerekli paketleri yükleyin:
```bash
pkg install python git
```

3. Repository'yi klonlayın:
```bash
git clone <repository-url>
cd <repository-name>
```

4. Python paketlerini yükleyin:
```bash
pip install -r requirements.txt
```

5. `.env` dosyasını oluşturun:
```bash
echo "BOT_TOKEN=your_bot_token" > .env
```

6. Botu çalıştırın:
```bash
python bot.py
```

## Arka Planda Çalıştırma (Termux)

Botu arka planda çalıştırmak için:
```bash
nohup python bot.py &
```

Bot'u durdurmak için:
```bash
pkill -f "python bot.py"
``` 