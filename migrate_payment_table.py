"""
Migration script to add the payments table to the database.
Run this script after updating your .env with Razorpay credentials.
"""
import sys
from sqlalchemy import create_engine, text
from app.core.config import settings
from app.core.database import Base
from app.models.payment import Payment

def migrate():
    print("Starting payment table migration...")
    
    try:
        engine = create_engine(settings.DATABASE_URL)
        
        # Create payments table
        Payment.__table__.create(bind=engine, checkfirst=True)
        
        print("✓ Payments table created successfully")
        
        # Verify table exists
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'payments')"
            ))
            exists = result.scalar()
            
            if exists:
                print("✓ Migration verified - payments table exists")
            else:
                print("✗ Migration verification failed")
                sys.exit(1)
        
        print("\nMigration completed successfully!")
        print("\nNext steps:")
        print("1. Add Razorpay credentials to your .env file:")
        print("   RAZORPAY_KEY_ID=your_key_id")
        print("   RAZORPAY_KEY_SECRET=your_key_secret")
        print("   RAZORPAY_WEBHOOK_SECRET=your_webhook_secret")
        print("2. Install razorpay package: pip install razorpay==1.4.2")
        print("3. Restart your application")
        
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    migrate()
