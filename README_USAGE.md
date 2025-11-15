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

## 📢 **Channel Configuration for Automated Posting**

### **Configure Your Telegram Channel:**

#### **1. Add Bot as Channel Administrator**
1. Go to your channel: `https://t.me/CheapAmazon3332234`
2. Click **"Add Member"**
3. Search for your bot: `@YourBotUsername`
4. Add as **Administrator** with **Post Messages** permission

#### **2. Configure Channel in Google Sheets**

**Create a worksheet called `campaigns` with this structure:**

| Campaign Name | Channels | Categories | Min Rating | Status |
|---------------|----------|------------|------------|--------|
| Cheap Amazon Deals | @CheapAmazon3332234 | electronics,home,kitchen | 4.0 | active |

**Channel Format Options:**
- ✅ `@CheapAmazon3332234` (recommended - username)
- ✅ `-1001234567890` (channel ID - if username doesn't work)

#### **3. Advanced Campaign Configuration**

**Full campaign parameters (JSON format):**
```json
{
  "name": "Cheap Amazon Deals",
  "channels": ["@CheapAmazon3332234"],
  "categories": ["electronics", "home", "kitchen"],
  "min_rating": 4.0,
  "content_template_id": "affiliate_deals",
  "product_filter_id": "top_rated",
  "posting_schedule_id": "daily_3pm",
  "status": "active"
}
```

### **🎯 Bot Posting Workflow:**

```
1. Campaign reads from Google Sheets ✅
2. Bot searches Amazon for top products ✅
3. AI generates engaging content ✅
4. Bot posts to @CheapAmazon3332234 ✅
5. Statistics logged automatically ✅
6. Next post scheduled ✅
```

## 🧪 **Testing Channel Posting:**

```bash
# Start bot
docker-compose up -d

# Check logs for posting activity
docker-compose logs -f bot

# Expected output:
# ✅ Posted to @CheapAmazon3332234 for campaign Cheap Amazon Deals
# ✅ Statistics logged for 1 posts
```

## 🎉 **Ready for Production!**

Your Telegram Affiliate Bot is now fully functional with:
- ✅ Working menu system
- ✅ Real Google Sheets integration
- ✅ Database operations
- ✅ Campaign management
- ✅ Statistics reporting
- ✅ **Automated posting to @CheapAmazon3332234**

**Send `/start` to your bot and start earning affiliate commissions! 💰🎊**
