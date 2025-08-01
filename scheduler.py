from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from database import SessionLocal, get_expiring_products
from datetime import date

async def check_expiring_products(bot):
    db = SessionLocal()
    try:
        expiring_products = get_expiring_products(db)
        for product in expiring_products:
            days_left = (product.expiry_date - date.today()).days
            message = (
                f"⚠️ UYARI: {product.name} ürününün son kullanma tarihine {days_left} gün kaldı!\n"
                f"Son Kullanma Tarihi: {product.expiry_date}\n"
                f"Kategori: {product.category or 'Belirtilmemiş'}"
            )
            await bot.send_message(chat_id=product.user.telegram_id, text=message)
    finally:
        db.close()

def setup_scheduler(bot):
    scheduler = BackgroundScheduler()
    
    # Her gün sabah 9'da kontrol et
    scheduler.add_job(
        lambda: check_expiring_products(bot),
        trigger=CronTrigger(hour=9, minute=0),
        id='check_expiring_products',
        name='Check products expiring soon',
        replace_existing=True
    )
    
    scheduler.start()
    return scheduler 