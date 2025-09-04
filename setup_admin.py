#!/usr/bin/env python3
"""
Setup script to create admin user for StudBud
"""
from app import app
from models import db, User

def create_admin_user():
    with app.app_context():
        # Check if admin user already exists
        existing_admin = User.query.filter_by(username='admin').first()
        if existing_admin:
            print("Admin user already exists. Updating password...")
            existing_admin.set_password('admin')
            existing_admin.is_admin = True
            existing_admin.role = 'admin'
        else:
            print("Creating new admin user...")
            admin_user = User(
                username='admin',
                role='admin',
                is_admin=True
            )
            admin_user.set_password('admin')
            db.session.add(admin_user)
        
        try:
            db.session.commit()
            print("✅ Admin user created/updated successfully!")
            print("   Username: admin")
            print("   Password: admin")
            print("   Role: admin")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error creating admin user: {e}")

if __name__ == '__main__':
    create_admin_user()