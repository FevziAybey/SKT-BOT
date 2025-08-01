import os
import logging
import cv2
import numpy as np
import pytesseract
import re
from PIL import Image
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, ConversationHandler, filters
from database import SessionLocal, create_user, get_user, add_product, get_user_products, delete_product

# Logging ayarları
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Tesseract yolunu ayarla
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# .env dosyasından token'ı yükle
load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Conversation states
MENU, PRODUCT_NAME, EXPIRY_DATE, DELETE_PRODUCT, WAITING_PHOTO, VERIFY_DATE = range(6)

# OCR işlevi
async def process_image_ocr(photo_path):
    try:
        # Görüntüyü oku
        image = cv2.imread(photo_path)
        original = image.copy()
        
        # Görüntü ön işleme fonksiyonları
        def preprocess_basic(img):
            # Temel ön işleme
            img = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            denoised = cv2.fastNlMeansDenoising(gray)
            return denoised
        
        def preprocess_adaptive(img):
            # Adaptif işleme
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
            return thresh
        
        def preprocess_advanced(img):
            # Gelişmiş ön işleme
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            ddepth = cv2.CV_32F
            gradX = cv2.Sobel(gray, ddepth=ddepth, dx=1, dy=0, ksize=-1)
            gradY = cv2.Sobel(gray, ddepth=ddepth, dx=0, dy=1, ksize=-1)
            gradient = cv2.subtract(gradX, gradY)
            gradient = cv2.convertScaleAbs(gradient)
            blurred = cv2.blur(gradient, (9, 9))
            (_, thresh) = cv2.threshold(blurred, 225, 255, cv2.THRESH_BINARY)
            return thresh

        # Farklı ön işleme yöntemleri ve OCR konfigürasyonları
        preprocessing_methods = [
            (preprocess_basic, '--oem 3 --psm 6 -l tur'),
            (preprocess_basic, '--oem 3 --psm 11 -l tur'),
            (preprocess_adaptive, '--oem 3 --psm 6 -l tur'),
            (preprocess_advanced, '--oem 3 --psm 6 -l tur'),
        ]
        
        # Geliştirilmiş tarih formatları ve regex pattern'leri
        date_patterns = {
            # Standart formatlar
            r'\d{2}[./]\d{2}[./]\d{4}': '%d.%m.%Y',  # DD/MM/YYYY veya DD.MM.YYYY
            r'\d{2}[./]\d{2}[./]\d{2}': '%d.%m.%y',   # DD/MM/YY veya DD.MM.YY
            
            # Esnek boşluklu formatlar
            r'(\d{2})\s*[./]\s*(\d{2})\s*[./]\s*(\d{2,4})': None,  # DD / MM / YYYY
            
            # SKT özel formatları
            r'SKT[:\s]*(\d{2})[./](\d{2})[./](\d{2,4})': None,  # SKT: DD/MM/YYYY
            r'S\.K\.T[:\s]*(\d{2})[./](\d{2})[./](\d{2,4})': None,  # S.K.T: DD/MM/YYYY
            r'Son\s*Kul\w*\s*Tar\w*[:\s]*(\d{2})[./](\d{2})[./](\d{2,4})': None,  # Son Kullanma Tarihi: DD/MM/YYYY
            
            # Ay isimleri ile formatlar
            r'(\d{1,2})\s*(OCAK|ŞUBAT|MART|NİSAN|MAYIS|HAZİRAN|TEMMUZ|AĞUSTOS|EYLÜL|EKİM|KASIM|ARALIK)\s*(\d{2,4})': 'month_name',
            r'(\d{1,2})\s*(OCA|ŞUB|MAR|NİS|MAY|HAZ|TEM|AĞU|EYL|EKİ|KAS|ARA)\s*(\d{2,4})': 'month_abbr',
            
            # Üretim/Son Kullanma formatları
            r'Üretim:\s*(\d{2})[./](\d{2})[./](\d{2,4}).*S\.?K\.?T\.?:?\s*(\d{2})[./](\d{2})[./](\d{2,4})': 'production_expiry'
        }

        # Ay isimlerini sayılara çevirme sözlüğü
        month_names = {
            'OCAK': '01', 'OCA': '01',
            'ŞUBAT': '02', 'ŞUB': '02',
            'MART': '03', 'MAR': '03',
            'NİSAN': '04', 'NİS': '04',
            'MAYIS': '05', 'MAY': '05',
            'HAZİRAN': '06', 'HAZ': '06',
            'TEMMUZ': '07', 'TEM': '07',
            'AĞUSTOS': '08', 'AĞU': '08',
            'EYLÜL': '09', 'EYL': '09',
            'EKİM': '10', 'EKİ': '10',
            'KASIM': '11', 'KAS': '11',
            'ARALIK': '12', 'ARA': '12'
        }

        all_results = []
        
        # Her ön işleme yöntemi ve OCR konfigürasyonu için dene
        for preprocess_func, config in preprocessing_methods:
            # Görüntüyü ön işle
            processed_image = preprocess_func(image.copy())
            
            # Debug için işlenmiş görüntüyü kaydet
            debug_filename = f'debug_{preprocessing_methods.index((preprocess_func, config))}.jpg'
            cv2.imwrite(debug_filename, processed_image)
            
            # OCR işlemi
            text = pytesseract.image_to_string(processed_image, config=config)
            logger.info(f"OCR Sonucu ({config}): {text}")
            
            # Her satırı ayrı ayrı kontrol et
            lines = text.split('\n')
            for line in lines:
                # Her pattern için kontrol et
                for pattern, format_type in date_patterns.items():
                    matches = re.finditer(pattern, line, re.IGNORECASE)
                    for match in matches:
                        try:
                            date_str = None
                            confidence = 1.0
                            production_date = None
                            
                            if format_type == 'month_name' or format_type == 'month_abbr':
                                # Ay isimli format
                                day, month_name, year = match.groups()
                                month = month_names.get(month_name.upper())
                                if month:
                                    day = day.zfill(2)
                                    if len(year) == 2:
                                        year = '20' + year
                                    date_str = f"{day}.{month}.{year}"
                                    confidence = 1.2  # Ay isimleri daha güvenilir
                            
                            elif format_type == 'production_expiry':
                                # Üretim ve SKT birlikte
                                prod_day, prod_month, prod_year, exp_day, exp_month, exp_year = match.groups()
                                if len(exp_year) == 2:
                                    exp_year = '20' + exp_year
                                if len(prod_year) == 2:
                                    prod_year = '20' + prod_year
                                date_str = f"{exp_day}.{exp_month}.{exp_year}"
                                production_date = f"{prod_day}.{prod_month}.{prod_year}"
                                confidence = 1.5  # İki tarih birden bulunduğu için daha güvenilir
                            
                            elif format_type:
                                # Standart format
                                date_str = match.group(0).replace('/', '.')
                                date_obj = datetime.strptime(date_str, format_type)
                                date_str = date_obj.strftime("%d.%m.%Y")
                            
                            else:
                                # Özel format (gruplar halinde)
                                if len(match.groups()) == 3:
                                    day, month, year = match.groups()
                                    if len(year) == 2:
                                        year = '20' + year
                                    date_str = f"{day.strip()}.{month.strip()}.{year.strip()}"
                            
                            if date_str:
                                # Tarihi doğrula
                                date_obj = datetime.strptime(date_str, "%d.%m.%Y")
                                
                                # Geçerlilik kontrolü
                                if date_obj.year >= 2000 and date_obj.year <= 2100:
                                    result = {
                                        'date_str': date_obj.strftime("%d.%m.%Y"),
                                        'confidence': confidence,
                                        'line': line.strip(),
                                        'production_date': production_date
                                    }
                                    all_results.append(result)
                                    
                        except (ValueError, AttributeError) as e:
                            logger.debug(f"Tarih ayrıştırma hatası: {str(e)}")
                            continue
        
        # Sonuçları değerlendir
        if all_results:
            # Güven skoruna göre sırala
            all_results.sort(key=lambda x: x['confidence'], reverse=True)
            
            # En yüksek güven skoruna sahip sonucu seç
            best_result = all_results[0]
            
            # Detaylı log
            logger.info(f"Tespit edilen en iyi sonuç: {best_result}")
            
            # Üretim tarihi varsa ekstra bilgi ekle
            if best_result['production_date']:
                return f"{best_result['date_str']} (Üretim: {best_result['production_date']})"
            
            return best_result['date_str']
        
        return None
        
    except Exception as e:
        logger.error(f"OCR işlemi sırasında hata: {str(e)}")
        return None

# Geçici dosyaları temizleme fonksiyonu
def cleanup_temp_files(user_id):
    try:
        # Kullanıcıya özel geçici dosyayı sil
        temp_file = f"temp_{user_id}.jpg"
        if os.path.exists(temp_file):
            os.remove(temp_file)
        
        # Debug görsellerini sil
        for i in range(4):  # preprocessing_methods sayısı kadar
            debug_file = f"debug_{i}.jpg"
            if os.path.exists(debug_file):
                os.remove(debug_file)
    except Exception as e:
        logger.error(f"Dosya temizleme hatası: {str(e)}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db = SessionLocal()
    
    try:
        db_user = get_user(db, user.id)
        if not db_user:
            create_user(db, user.id, user.username)
    finally:
        db.close()
    
    keyboard = [
        ["➕ Ürün Ekle", "📋 Ürünleri Listele"],
        ["⚠️ Yaklaşan SKT'ler", "🗑️ Ürün Sil"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f"Merhaba {user.first_name}! 🎉\n\n"
        "SKT Kontrol Botuna hoş geldiniz.\n"
        "Lütfen aşağıdaki menüden bir işlem seçin:",
        reply_markup=reply_markup
    )
    return MENU

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == "➕ Ürün Ekle":
        keyboard = [
            ["📝 Manuel Giriş", "📸 Fotoğraftan SKT Okut"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Lütfen ekleme yöntemini seçin:",
            reply_markup=reply_markup
        )
        return PRODUCT_NAME
    elif text == "📋 Ürünleri Listele":
        await list_products(update, context)
        return MENU
    elif text == "🗑️ Ürün Sil":
        await show_delete_menu(update, context)
        return DELETE_PRODUCT
    elif text == "⚠️ Yaklaşan SKT'ler":
        await show_expiring_products(update, context)
        return MENU
    
    return MENU

async def get_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == "🔙 Ana Menü":
        return await return_to_main_menu(update, context)
    elif text == "📸 Fotoğraftan SKT Okut" or text == "📸 Tekrar Dene":
        await update.message.reply_text(
            "Lütfen ürünün son kullanma tarihinin olduğu kısmın fotoğrafını gönderin."
        )
        return WAITING_PHOTO
    elif text == "📝 Manuel Giriş":
        keyboard = [
            ["🔙 Ana Menü"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "Lütfen ürün adını girin:",
            reply_markup=reply_markup
        )
        context.user_data['input_method'] = 'manual'
        return PRODUCT_NAME
    else:
        if context.user_data.get('input_method') == 'manual':
            context.user_data['product_name'] = text
            keyboard = [
                ["🔙 Ana Menü"]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await update.message.reply_text(
                "Lütfen son kullanma tarihini GG.AA.YYYY formatında girin:\n"
                "Örnek: 31.12.2024",
                reply_markup=reply_markup
            )
            return EXPIRY_DATE
        elif context.user_data.get('input_method') == 'ocr':
            context.user_data['product_name'] = text
            db = SessionLocal()
            try:
                user = get_user(db, update.effective_user.id)
                expiry_date = datetime.strptime(context.user_data['detected_date'], "%d.%m.%Y").date()
                add_product(
                    db,
                    user.id,
                    context.user_data['product_name'],
                    expiry_date
                )
                
                await return_to_main_menu(update, context, "✅ Ürün başarıyla eklendi!")
                return MENU
            finally:
                db.close()
    
    return MENU

async def return_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, message=None):
    keyboard = [
        ["➕ Ürün Ekle", "📋 Ürünleri Listele"],
        ["⚠️ Yaklaşan SKT'ler", "🗑️ Ürün Sil"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    if message:
        await update.message.reply_text(message, reply_markup=reply_markup)
    else:
        await update.message.reply_text(
            "Ana menüye dönüldü.\n"
            "Lütfen bir işlem seçin:",
            reply_markup=reply_markup
        )
    return MENU

async def get_expiry_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == "🔙 Ana Menü":
        return await return_to_main_menu(update, context)
        
    try:
        date_text = update.message.text
        expiry_date = datetime.strptime(date_text, "%d.%m.%Y").date()
        
        db = SessionLocal()
        try:
            user = get_user(db, update.effective_user.id)
            add_product(
                db,
                user.id,
                context.user_data['product_name'],
                expiry_date
            )
        finally:
            db.close()
        
        await return_to_main_menu(update, context, "✅ Ürün başarıyla eklendi!")
        return MENU
        
    except ValueError:
        keyboard = [
            ["🔙 Ana Menü"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "❌ Geçersiz tarih formatı! Lütfen GG.AA.YYYY formatında tekrar girin:\n"
            "Örnek: 31.12.2024",
            reply_markup=reply_markup
        )
        return EXPIRY_DATE

async def list_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = SessionLocal()
    try:
        user = get_user(db, update.effective_user.id)
        products = get_user_products(db, user.id)
        
        if not products:
            await update.message.reply_text("📭 Henüz kayıtlı ürününüz bulunmamaktadır.")
            return
        
        message = "📋 Ürün Listesi:\n\n"
        for product in products:
            days_left = (product.expiry_date - datetime.now().date()).days
            status = "🟢" if days_left > 7 else "🟡" if days_left > 0 else "🔴"
            
            message += (
                f"{status} {product.name}\n"
                f"SKT: {product.expiry_date.strftime('%d.%m.%Y')} ({days_left} gün kaldı)\n"
                f"ID: {product.id}\n\n"
            )
        
        await update.message.reply_text(message)
    finally:
        db.close()

async def show_delete_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = SessionLocal()
    try:
        user = get_user(db, update.effective_user.id)
        products = get_user_products(db, user.id)
        
        if not products:
            await update.message.reply_text("📭 Silinecek ürün bulunmamaktadır.")
            return MENU
        
        message = "🗑️ Silmek istediğiniz ürünün ID'sini girin:\n\n"
        for product in products:
            message += f"ID: {product.id} - {product.name}\n"
        
        await update.message.reply_text(message)
        return DELETE_PRODUCT
    finally:
        db.close()

async def delete_product_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        product_id = int(update.message.text)
        db = SessionLocal()
        try:
            user = get_user(db, update.effective_user.id)
            if delete_product(db, product_id, user.id):
                await update.message.reply_text("✅ Ürün başarıyla silindi!")
            else:
                await update.message.reply_text("❌ Ürün bulunamadı veya size ait değil!")
        finally:
            db.close()
    except ValueError:
        await update.message.reply_text("❌ Geçersiz ID! Lütfen sayısal bir ID girin.")
    
    return MENU

async def show_expiring_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = SessionLocal()
    try:
        user = get_user(db, update.effective_user.id)
        products = get_user_products(db, user.id)
        
        if not products:
            await update.message.reply_text("📭 Henüz kayıtlı ürününüz bulunmamaktadır.")
            return
        
        expiring_products = []
        for product in products:
            days_left = (product.expiry_date - datetime.now().date()).days
            if days_left <= 7:
                expiring_products.append((product, days_left))
        
        if not expiring_products:
            await update.message.reply_text("✅ 7 gün içinde son kullanma tarihi yaklaşan ürününüz bulunmamaktadır.")
            return
        
        message = "⚠️ Yaklaşan Son Kullanma Tarihleri:\n\n"
        for product, days_left in expiring_products:
            status = "🟡" if days_left > 0 else "🔴"
            
            if days_left <= 0:
                durum = "SON KULLANMA TARİHİ GEÇMİŞ!"
            else:
                durum = f"{days_left} gün kaldı"
            
            message += (
                f"{status} {product.name}\n"
                f"SKT: {product.expiry_date.strftime('%d.%m.%Y')} ({durum})\n"
                f"ID: {product.id}\n\n"
            )
        
        await update.message.reply_text(message)
    finally:
        db.close()

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("İşlem iptal edildi.")
    return MENU

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Fotoğrafı indir
        photo = await update.message.photo[-1].get_file()
        photo_path = f"temp_{update.effective_user.id}.jpg"
        await photo.download_to_drive(photo_path)
        
        # OCR işlemi
        date_str = await process_image_ocr(photo_path)
        
        # Tüm geçici dosyaları temizle
        cleanup_temp_files(update.effective_user.id)
        
        if date_str:
            keyboard = [
                ["✅ Doğru", "❌ Yanlış"]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await update.message.reply_text(
                f"Tespit edilen tarih: {date_str}\n\n"
                "Bu tarih doğru mu?",
                reply_markup=reply_markup
            )
            context.user_data['detected_date'] = date_str
            return VERIFY_DATE
        else:
            keyboard = [
                ["📝 Manuel Giriş", "📸 Tekrar Dene"]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await update.message.reply_text(
                "❌ Son kullanma tarihi tespit edilemedi.\n"
                "Lütfen seçim yapın:",
                reply_markup=reply_markup
            )
            return PRODUCT_NAME
            
    except Exception as e:
        logger.error(f"Fotoğraf işleme hatası: {str(e)}")
        # Hata durumunda da dosyaları temizle
        cleanup_temp_files(update.effective_user.id)
        
        keyboard = [
            ["📝 Manuel Giriş", "📸 Tekrar Dene"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "❌ Fotoğraf işlenirken bir hata oluştu.\n"
            "Lütfen seçim yapın:",
            reply_markup=reply_markup
        )
        return PRODUCT_NAME

async def verify_date_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == "✅ Doğru":
        keyboard = [
            ["🔙 Ana Menü"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "Lütfen ürün adını girin:",
            reply_markup=reply_markup
        )
        context.user_data['input_method'] = 'ocr'
        return PRODUCT_NAME
    elif text == "❌ Yanlış":
        keyboard = [
            ["📝 Manuel Giriş", "📸 Tekrar Dene", "🔙 Ana Menü"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "Lütfen seçim yapın:",
            reply_markup=reply_markup
        )
        return PRODUCT_NAME

def main():
    application = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MENU: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, menu_handler)
            ],
            PRODUCT_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_product_name)
            ],
            EXPIRY_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_expiry_date)
            ],
            DELETE_PRODUCT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, delete_product_handler)
            ],
            WAITING_PHOTO: [
                MessageHandler(filters.PHOTO, photo_handler)
            ],
            VERIFY_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, verify_date_handler)
            ]
        },
        fallbacks=[CommandHandler('iptal', cancel)]
    )
    
    application.add_handler(conv_handler)
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main() 