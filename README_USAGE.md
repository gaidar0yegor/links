# 🚀 Telegram Affiliate Bot - Complete Usage Guide

## 🎯 **Quick Start - Everything Working!**

Your bot is now fully operational with all fixes applied. Here's how to use it:

### **1. Start the Bot**
```bash
cd /home/user/telegram_affiliate_bot
docker-compose up -d
```

### **2. Test in Telegram**

#### **Basic Commands:**
- Send `/start` → Authorization & Main Menu
- Send `/menu` → Show Main Menu

#### **Main Menu (2 Buttons):**
1. **"Рекламные кампании"** → Campaign Management
2. **"Статистика"** → Sales Statistics

### **3. Campaign Management Features:**
- ✅ View existing campaigns
- ✅ Create new campaigns
- ✅ Edit campaign settings
- ✅ Set posting schedules
- ✅ Start/stop campaigns

### **4. Statistics Features:**
- ✅ View real sales data from Google Sheets
- ✅ Revenue, clicks, sales metrics
- ✅ Refresh data button

## 🔧 **System Status - All Green:**

✅ **Menu Buttons:** Working (fixed callback handlers)  
✅ **Google Sheets:** Real data (initialized worksheets)  
✅ **Database:** PostgreSQL with 4 campaigns  
✅ **Authorization:** Working with whitelist  
✅ **All APIs:** Amazon, Gemini, Sheets connected  

## 🧪 **Test Commands:**

```bash
# Check if bot is running
docker-compose ps

# View bot logs
docker-compose logs bot | tail -20

# Run full system test
docker-compose exec bot python test_all_components.py

# Restart bot
docker-compose restart
```

## 📋 **Google Sheets Worksheets Created:**

1. **`users_whitelist`** - Authorized users
2. **`rewrite_prompt`** - AI prompts
3. **`utm_marks`** - Tracking parameters
4. **`statistics`** - Sales data

## 🎉 **Ready for Production!**

Your Telegram Affiliate Bot is now fully functional with:
- ✅ Working menu system
- ✅ Real Google Sheets integration
- ✅ Database operations
- ✅ Campaign management
- ✅ Statistics reporting
- ✅ Automated posting (when configured)

**Send `/start` to your bot and enjoy! 🎊**
