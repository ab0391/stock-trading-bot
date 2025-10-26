#!/usr/bin/env python3
"""
Stock Trading Bot - Ready for Strategy Upload
This bot is designed to work with stock trading strategies (Apple, Tesla, etc.)
"""

import yfinance as yf
import pandas as pd
import numpy as np
import requests
import json
import time
import os
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class StockTradingBot:
    def __init__(self):
        self.telegram_token = os.getenv('TELEGRAM_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.supported_stocks = ['AAPL', 'TSLA', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'NFLX']
        self.active_trades = {}
        self.trades_history = []
        
        # Load existing data
        self.load_trades_data()
        
        print("📈 Stock Trading Bot initialized")
        print(f"📊 Supported stocks: {', '.join(self.supported_stocks)}")
        print("⏳ Waiting for strategy to be uploaded...")

    def load_trades_data(self):
        """Load existing trades data"""
        try:
            if os.path.exists('active_trades.json'):
                with open('active_trades.json', 'r') as f:
                    self.active_trades = json.load(f)
            
            if os.path.exists('trades_history.json'):
                with open('trades_history.json', 'r') as f:
                    self.trades_history = json.load(f)
        except Exception as e:
            print(f"⚠️ Error loading trades data: {e}")

    def save_trades_data(self):
        """Save trades data to files"""
        try:
            with open('active_trades.json', 'w') as f:
                json.dump(self.active_trades, f, indent=2)
            
            with open('trades_history.json', 'w') as f:
                json.dump(self.trades_history, f, indent=2)
        except Exception as e:
            print(f"⚠️ Error saving trades data: {e}")

    def get_stock_price(self, symbol):
        """Get current stock price"""
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="1d", interval="1m")
            if not data.empty:
                return float(data['Close'].iloc[-1])
            return None
        except Exception as e:
            print(f"❌ Error getting price for {symbol}: {e}")
            return None

    def send_telegram_message(self, message):
        """Send message to Telegram"""
        if not self.telegram_token or not self.telegram_chat_id:
            print("⚠️ Telegram not configured")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            data = {
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            response = requests.post(url, data=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Error sending Telegram message: {e}")
            return False

    def process_signal(self, signal_data):
        """
        Process trading signal - TO BE IMPLEMENTED WITH STRATEGY
        This method will be customized based on the uploaded strategy
        """
        print(f"📊 Processing signal: {signal_data}")
        # TODO: Implement strategy-specific logic here
        pass

    def run(self):
        """Main bot loop"""
        print("🚀 Stock Trading Bot started")
        print("📋 Ready to receive strategy implementation")
        
        # Send startup message
        self.send_telegram_message(
            "🚀 <b>Stock Trading Bot Started</b>\n"
            "📈 Ready for strategy implementation\n"
            "⏰ " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        
        while True:
            try:
                # Check for new signals or implement strategy logic here
                # This will be customized based on the uploaded strategy
                
                time.sleep(60)  # Check every minute
                
            except KeyboardInterrupt:
                print("\n🛑 Bot stopped by user")
                break
            except Exception as e:
                print(f"❌ Error in main loop: {e}")
                time.sleep(60)

if __name__ == "__main__":
    bot = StockTradingBot()
    bot.run()
