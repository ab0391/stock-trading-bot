#!/usr/bin/env python3
"""
Opening Range Breakout (ORB) Stock Trading Bot
Implements the complete ORB strategy for automated trading
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

class ORBStockTradingBot:
    def __init__(self):
        # Telegram configuration
        self.telegram_token = os.getenv('TELEGRAM_TOKEN', '8212205627:AAEpn-8ReZkBtoI4iHJbJxcHn8llSj2JtY4')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        # Trading configuration
        self.supported_stocks = ['AAPL', 'TSLA', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'NFLX']
        self.account_size = float(os.getenv('ACCOUNT_SIZE', '50000'))  # Default $50k
        self.risk_per_trade = float(os.getenv('RISK_PER_TRADE', '0.01'))  # 1% default
        
        # Strategy parameters
        self.opening_range_minutes = 30  # 9:30 AM - 10:00 AM EST
        self.min_risk_reward = 2.0  # Minimum 2:1 RR
        self.max_trades_per_day = 3
        self.max_daily_loss = 0.03  # 3% of account
        
        # Market hours
        self.est_tz = pytz.timezone('US/Eastern')
        self.market_open = datetime.now(self.est_tz).replace(hour=9, minute=30, second=0, microsecond=0)
        self.market_close = datetime.now(self.est_tz).replace(hour=16, minute=0, second=0, microsecond=0)
        
        # Data storage
        self.active_trades = {}
        self.trades_history = []
        self.daily_stats = {
            'trades_today': 0,
            'daily_pnl': 0.0,
            'consecutive_losses': 0
        }
        
        # Opening range data
        self.opening_ranges = {}
        self.volume_averages = {}
        
        # Load existing data
        self.load_trades_data()
        
        print("📈 ORB Stock Trading Bot initialized")
        print(f"📊 Supported stocks: {', '.join(self.supported_stocks)}")
        print(f"💰 Account size: ${self.account_size:,.2f}")
        print(f"🎯 Risk per trade: {self.risk_per_trade*100:.1f}%")

    def load_trades_data(self):
        """Load existing trades data"""
        try:
            if os.path.exists('active_trades.json'):
                with open('active_trades.json', 'r') as f:
                    self.active_trades = json.load(f)
            
            if os.path.exists('trades_history.json'):
                with open('trades_history.json', 'r') as f:
                    self.trades_history = json.load(f)
                    
            if os.path.exists('daily_stats.json'):
                with open('daily_stats.json', 'r') as f:
                    self.daily_stats = json.load(f)
        except Exception as e:
            print(f"⚠️ Error loading trades data: {e}")

    def save_trades_data(self):
        """Save trades data to files"""
        try:
            with open('active_trades.json', 'w') as f:
                json.dump(self.active_trades, f, indent=2)
            
            with open('trades_history.json', 'w') as f:
                json.dump(self.trades_history, f, indent=2)
                
            with open('daily_stats.json', 'w') as f:
                json.dump(self.daily_stats, f, indent=2)
        except Exception as e:
            print(f"⚠️ Error saving trades data: {e}")

    def get_stock_data(self, symbol, period="1d", interval="5m"):
        """Get stock data from Yahoo Finance"""
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period=period, interval=interval)
            if not data.empty:
                return data
            return None
        except Exception as e:
            print(f"❌ Error getting data for {symbol}: {e}")
            return None

    def calculate_volume_average(self, symbol, data):
        """Calculate 20-period volume average"""
        try:
            if len(data) >= 20:
                return data['Volume'].tail(20).mean()
            return data['Volume'].mean() if not data.empty else 0
        except Exception as e:
            print(f"❌ Error calculating volume average for {symbol}: {e}")
            return 0

    def is_market_open(self):
        """Check if US stock market is open"""
        now = datetime.now(self.est_tz)
        weekday = now.weekday()
        
        # Market closed on weekends
        if weekday >= 5:
            return False, "Weekend - Market closed"
        
        # Check market hours (9:30 AM - 4:00 PM EST)
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        
        if market_open <= now <= market_close:
            return True, "Market open"
        
        return False, "Outside market hours"

    def is_opening_range_period(self):
        """Check if we're in the opening range period (9:30-10:00 AM EST)"""
        now = datetime.now(self.est_tz)
        weekday = now.weekday()
        
        if weekday >= 5:  # Weekend
            return False
        
        opening_start = now.replace(hour=9, minute=30, second=0, microsecond=0)
        opening_end = now.replace(hour=10, minute=0, second=0, microsecond=0)
        
        return opening_start <= now <= opening_end

    def calculate_opening_range(self, symbol):
        """Calculate opening range for a symbol"""
        try:
            # Get 5-minute data for today
            data = self.get_stock_data(symbol, period="1d", interval="5m")
            if data is None or data.empty:
                return None
            
            # Filter for opening range period (first 30 minutes = 6 candles of 5min each)
            opening_data = data.head(6)
            
            if opening_data.empty:
                return None
            
            orh = opening_data['High'].max()
            orl = opening_data['Low'].min()
            range_size = orh - orl
            
            # Calculate volume average
            volume_avg = self.calculate_volume_average(symbol, data)
            
            opening_range = {
                'symbol': symbol,
                'orh': float(orh),
                'orl': float(orl),
                'range_size': float(range_size),
                'volume_avg': float(volume_avg),
                'timestamp': datetime.now().isoformat()
            }
            
            self.opening_ranges[symbol] = opening_range
            return opening_range
            
        except Exception as e:
            print(f"❌ Error calculating opening range for {symbol}: {e}")
            return None

    def check_breakout_conditions(self, symbol, current_price, current_volume):
        """Check if breakout conditions are met"""
        if symbol not in self.opening_ranges:
            return None, "No opening range data"
        
        orb = self.opening_ranges[symbol]
        orh = orb['orh']
        orl = orb['orl']
        volume_avg = orb['volume_avg']
        
        # Check volume condition (1.5x average)
        volume_condition = current_volume >= (volume_avg * 1.5)
        
        # Check breakout conditions
        if current_price > orh:
            return {
                'direction': 'LONG',
                'entry_price': orh + 0.05,
                'stop_loss': orl - 0.10,
                'target1': orh + 0.05 + (2 * (orh + 0.05 - (orl - 0.10))),
                'target2': orh + 0.05 + (3 * (orh + 0.05 - (orl - 0.10))),
                'target3': orh + 0.05 + (2 * orb['range_size']),
                'volume_ok': volume_condition
            }, "Bullish breakout detected"
        
        elif current_price < orl:
            return {
                'direction': 'SHORT',
                'entry_price': orl - 0.05,
                'stop_loss': orh + 0.10,
                'target1': orl - 0.05 - (2 * ((orh + 0.10) - (orl - 0.05))),
                'target2': orl - 0.05 - (3 * ((orh + 0.10) - (orl - 0.05))),
                'target3': orl - 0.05 - (2 * orb['range_size']),
                'volume_ok': volume_condition
            }, "Bearish breakdown detected"
        
        return None, "No breakout detected"

    def calculate_position_size(self, entry_price, stop_loss):
        """Calculate position size based on risk management"""
        try:
            risk_per_share = abs(entry_price - stop_loss)
            if risk_per_share <= 0:
                return 0
            
            risk_amount = self.account_size * self.risk_per_trade
            position_size = int(risk_amount / risk_per_share)
            
            # Ensure we don't risk more than 2% of account
            max_position_value = self.account_size * 0.02
            max_shares = int(max_position_value / entry_price)
            
            return min(position_size, max_shares)
            
        except Exception as e:
            print(f"❌ Error calculating position size: {e}")
            return 0

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

    def execute_trade(self, symbol, trade_data):
        """Execute a trade based on ORB strategy"""
        try:
            # Check daily limits
            if self.daily_stats['trades_today'] >= self.max_trades_per_day:
                return False, "Daily trade limit reached"
            
            if abs(self.daily_stats['daily_pnl']) >= (self.account_size * self.max_daily_loss):
                return False, "Daily loss limit reached"
            
            # Calculate position size
            position_size = self.calculate_position_size(
                trade_data['entry_price'], 
                trade_data['stop_loss']
            )
            
            if position_size <= 0:
                return False, "Position size too small"
            
            # Create trade record
            trade = {
                'id': f"{symbol}_{int(time.time())}",
                'symbol': symbol,
                'direction': trade_data['direction'],
                'entry_price': trade_data['entry_price'],
                'stop_loss': trade_data['stop_loss'],
                'target1': trade_data['target1'],
                'target2': trade_data['target2'],
                'target3': trade_data['target3'],
                'position_size': position_size,
                'risk_amount': position_size * abs(trade_data['entry_price'] - trade_data['stop_loss']),
                'timestamp': datetime.now().isoformat(),
                'status': 'ACTIVE',
                'tp1_hit': False,
                'tp2_hit': False,
                'current_stop': trade_data['stop_loss']
            }
            
            # Add to active trades
            self.active_trades[trade['id']] = trade
            
            # Update daily stats
            self.daily_stats['trades_today'] += 1
            
            # Send Telegram notification
            message = f"""
🚀 <b>ORB Trade Executed</b>

📊 <b>Symbol:</b> {symbol}
📈 <b>Direction:</b> {trade_data['direction']}
💰 <b>Entry:</b> ${trade_data['entry_price']:.2f}
🛑 <b>Stop Loss:</b> ${trade_data['stop_loss']:.2f}
🎯 <b>Target 1:</b> ${trade_data['target1']:.2f}
🎯 <b>Target 2:</b> ${trade_data['target2']:.2f}
🎯 <b>Target 3:</b> ${trade_data['target3']:.2f}
📦 <b>Position Size:</b> {position_size} shares
💵 <b>Risk Amount:</b> ${trade['risk_amount']:.2f}
⏰ <b>Time:</b> {datetime.now().strftime('%H:%M:%S')}
            """
            
            self.send_telegram_message(message)
            
            # Save data
            self.save_trades_data()
            
            return True, f"Trade executed: {trade['id']}"
            
        except Exception as e:
            print(f"❌ Error executing trade: {e}")
            return False, str(e)

    def monitor_active_trades(self):
        """Monitor and manage active trades"""
        try:
            for trade_id, trade in list(self.active_trades.items()):
                symbol = trade['symbol']
                
                # Get current price
                data = self.get_stock_data(symbol, period="1d", interval="1m")
                if data is None or data.empty:
                    continue
                
                current_price = float(data['Close'].iloc[-1])
                
                # Check stop loss
                if trade['direction'] == 'LONG' and current_price <= trade['current_stop']:
                    self.close_trade(trade_id, current_price, "Stop Loss Hit")
                    continue
                elif trade['direction'] == 'SHORT' and current_price >= trade['current_stop']:
                    self.close_trade(trade_id, current_price, "Stop Loss Hit")
                    continue
                
                # Check take profit targets
                if trade['direction'] == 'LONG':
                    if not trade['tp1_hit'] and current_price >= trade['target1']:
                        self.hit_take_profit(trade_id, 1, current_price)
                    elif not trade['tp2_hit'] and current_price >= trade['target2']:
                        self.hit_take_profit(trade_id, 2, current_price)
                    elif current_price >= trade['target3']:
                        self.close_trade(trade_id, current_price, "Target 3 Hit")
                
                elif trade['direction'] == 'SHORT':
                    if not trade['tp1_hit'] and current_price <= trade['target1']:
                        self.hit_take_profit(trade_id, 1, current_price)
                    elif not trade['tp2_hit'] and current_price <= trade['target2']:
                        self.hit_take_profit(trade_id, 2, current_price)
                    elif current_price <= trade['target3']:
                        self.close_trade(trade_id, current_price, "Target 3 Hit")
                
                # Update trailing stop after TP1
                if trade['tp1_hit'] and not trade['tp2_hit']:
                    if trade['direction'] == 'LONG':
                        new_stop = trade['entry_price']  # Breakeven
                        if new_stop > trade['current_stop']:
                            trade['current_stop'] = new_stop
                    elif trade['direction'] == 'SHORT':
                        new_stop = trade['entry_price']  # Breakeven
                        if new_stop < trade['current_stop']:
                            trade['current_stop'] = new_stop
                
        except Exception as e:
            print(f"❌ Error monitoring trades: {e}")

    def hit_take_profit(self, trade_id, tp_level, price):
        """Handle take profit hit"""
        try:
            trade = self.active_trades[trade_id]
            
            if tp_level == 1:
                trade['tp1_hit'] = True
                # Close 50% of position
                trade['position_size'] = int(trade['position_size'] * 0.5)
                message = f"🎯 <b>Target 1 Hit!</b>\n{symbol}: ${price:.2f}\n50% position closed"
            elif tp_level == 2:
                trade['tp2_hit'] = True
                # Close 25% more (75% total closed)
                trade['position_size'] = int(trade['position_size'] * 0.25)
                message = f"🎯 <b>Target 2 Hit!</b>\n{symbol}: ${price:.2f}\n75% position closed"
            
            self.send_telegram_message(message)
            self.save_trades_data()
            
        except Exception as e:
            print(f"❌ Error handling take profit: {e}")

    def close_trade(self, trade_id, exit_price, reason):
        """Close a trade"""
        try:
            trade = self.active_trades[trade_id]
            
            # Calculate P&L
            if trade['direction'] == 'LONG':
                pnl = (exit_price - trade['entry_price']) * trade['position_size']
            else:
                pnl = (trade['entry_price'] - exit_price) * trade['position_size']
            
            # Update trade record
            trade['exit_price'] = exit_price
            trade['exit_reason'] = reason
            trade['pnl'] = pnl
            trade['status'] = 'CLOSED'
            trade['exit_time'] = datetime.now().isoformat()
            
            # Move to history
            self.trades_history.append(trade)
            del self.active_trades[trade_id]
            
            # Update daily stats
            self.daily_stats['daily_pnl'] += pnl
            if pnl < 0:
                self.daily_stats['consecutive_losses'] += 1
            else:
                self.daily_stats['consecutive_losses'] = 0
            
            # Send notification
            pnl_emoji = "💰" if pnl > 0 else "📉"
            message = f"""
{pnl_emoji} <b>Trade Closed</b>

📊 <b>Symbol:</b> {trade['symbol']}
📈 <b>Direction:</b> {trade['direction']}
💰 <b>Entry:</b> ${trade['entry_price']:.2f}
💵 <b>Exit:</b> ${exit_price:.2f}
📦 <b>Shares:</b> {trade['position_size']}
💸 <b>P&L:</b> ${pnl:.2f}
📝 <b>Reason:</b> {reason}
⏰ <b>Time:</b> {datetime.now().strftime('%H:%M:%S')}
            """
            
            self.send_telegram_message(message)
            self.save_trades_data()
            
        except Exception as e:
            print(f"❌ Error closing trade: {e}")

    def run(self):
        """Main bot loop"""
        print("🚀 ORB Stock Trading Bot started")
        
        # Send startup message
        self.send_telegram_message(
            "🚀 <b>ORB Stock Trading Bot Started</b>\n"
            "📈 Opening Range Breakout Strategy Active\n"
            "⏰ " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        
        last_opening_range_calc = None
        
        while True:
            try:
                now = datetime.now(self.est_tz)
                is_open, status = self.is_market_open()
                
                if not is_open:
                    print(f"⏰ Market closed: {status}")
                    time.sleep(300)  # Check every 5 minutes when closed
                    continue
                
                # Calculate opening ranges during opening period
                if self.is_opening_range_period():
                    if last_opening_range_calc != now.date():
                        print("📊 Calculating opening ranges...")
                        for symbol in self.supported_stocks:
                            self.calculate_opening_range(symbol)
                        last_opening_range_calc = now.date()
                
                # Monitor active trades
                if self.active_trades:
                    self.monitor_active_trades()
                
                # Check for new breakouts (only after opening range period)
                if not self.is_opening_range_period() and self.opening_ranges:
                    for symbol in self.supported_stocks:
                        if symbol in self.opening_ranges:
                            # Get current data
                            data = self.get_stock_data(symbol, period="1d", interval="1m")
                            if data is None or data.empty:
                                continue
                            
                            current_price = float(data['Close'].iloc[-1])
                            current_volume = float(data['Volume'].iloc[-1])
                            
                            # Check for breakout
                            breakout_data, message = self.check_breakout_conditions(
                                symbol, current_price, current_volume
                            )
                            
                            if breakout_data and breakout_data['volume_ok']:
                                # Check if we already have a trade for this symbol
                                has_active_trade = any(
                                    trade['symbol'] == symbol and trade['status'] == 'ACTIVE'
                                    for trade in self.active_trades.values()
                                )
                                
                                if not has_active_trade:
                                    success, result = self.execute_trade(symbol, breakout_data)
                                    if success:
                                        print(f"✅ {message}: {result}")
                                    else:
                                        print(f"❌ Trade failed: {result}")
                
                # Close all positions before market close
                if now.hour == 15 and now.minute >= 45:  # 3:45 PM
                    for trade_id in list(self.active_trades.keys()):
                        trade = self.active_trades[trade_id]
                        data = self.get_stock_data(trade['symbol'], period="1d", interval="1m")
                        if data is not None and not data.empty:
                            current_price = float(data['Close'].iloc[-1])
                            self.close_trade(trade_id, current_price, "End of Day Close")
                
                time.sleep(60)  # Check every minute during market hours
                
            except KeyboardInterrupt:
                print("\n🛑 Bot stopped by user")
                break
            except Exception as e:
                print(f"❌ Error in main loop: {e}")
                time.sleep(60)

if __name__ == "__main__":
    bot = ORBStockTradingBot()
    bot.run()
