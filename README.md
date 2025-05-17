# Automated-Telegram-Media-Uploader
Advanced Telegram Media Uploader: Secure, Resumable, and Concurrent Multi-Bot Uploader
# Telegram Media Uploader

This is a professional-grade Telegram Media Uploader script designed for fast, secure, and reliable uploading of photos and videos to Telegram using multiple bots.

## 🚀 Features
- 📂 Supports uploading media files (photos and videos) from a specified parent folder with multiple subfolders.
- 🚀 Fast, concurrent uploading using 10 bots (5 for photos, 5 for videos).
- ✅ Resumes uploads from where it left off using a log file.
- ⚡ Secure: Uses environment variables for sensitive data (bot tokens, chat IDs).
- 📝 Detailed logging: Separate logs for successfully uploaded files and oversized files.
- 🔄 Adaptive cooldown with retry mechanism for failed uploads.

---

## ⚡ Requirements
- Python 3.8+
- Telegram Bot Tokens (5 for photos, 5 for videos)
- Chat IDs for the target Telegram groups or channels

---

## 📦 Setup

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/telegram-media-uploader.git
cd telegram-media-uploader
