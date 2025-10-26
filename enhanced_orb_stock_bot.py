#!/usr/bin/env python3
"""
Enhanced Opening Range Breakout (ORB) Stock Trading Bot
- UK and US stocks for Dubai-based trading
- Dynamic risk-reward ratios (2:1 to 5:1)
- Multi-timeframe confirmation
- Enhanced volume analysis
- Dubai timezone optimization
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

class EnhancedORBStockTradingBot:
    def __init__(self):
        # Telegram configuration
        self.telegram_token = os.getenv('TELEGRAM_TOKEN', '8212205627:AAEpn-8ReZkBtoI4iHJbJxcHn8llSj2JtY4')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        # Trading configuration
        self.us_stocks = ['AAPL', 'TSLA', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'NFLX']
        self.uk_stocks = ['LLOY.L', 'VOD.L', 'BARC.L', 'TSCO.L', 'BP.L', 'AZN.L', 'ULVR.L', 'SHEL.L']
        self.all_stocks = self.us_stocks + self.uk_stocks
        
        self.account_size = float(os.getenv('ACCOUNT_SIZE', '50000'))  # Default $50k
        self.risk_per_trade = float(os.getenv('RISK_PER_TRADE', '0.01'))  # 1% default
        
        # Strategy parameters
        self.opening_range_minutes = 30  # 9:30 AM - 10:00 AM EST / 8:00 AM - 8:30 AM GMT
        self.min_risk_reward = 2.0  # Minimum 2:1 RR
        self.max_risk_reward = 5.0  # Maximum 5:1 RR
        self.max_trades_per_day = 5  # Increased for more opportunities
        self.max_daily_loss = 0.03  # 3% of account
        
        # Timezone configuration for Dubai
        self.dubai_tz = pytz.timezone('Asia/Dubai')
        self.ny_tz = pytz.timezone('US/Eastern')
        self.london_tz = pytz.timezone('Europe/London')
        
        # Data storage
        self.active_trades = {}
        self.trades_history = []
        self.daily_stats = {
            'trades_today': 0,
            'daily_pnl': 0.0,
            'consecutive_losses': 0,
            'win_rate': 0.0,
            'avg_rr_achieved': 0.0
        }
        
        # Opening range data
        self.opening_ranges = {}
        self.volume_averages = {}
        self.market_conditions = {}
        
        # Load existing data
        self.load_trades_data()
        
        print("📈 Enhanced ORB Stock Trading Bot initialized")
        print(f"🇺🇸 US Stocks: {', '.join(self.us_stocks)}")
        print(f"🇬🇧 UK Stocks: {', '.join(self.uk_stocks)}")
        print(f"💰 Account size: ${self.account_size:,.2f}")
        print(f"🎯 Risk per trade: {self.risk_per_trade*100:.1f}%")
        print(f"📊 Total stocks: {len(self.all_stocks)}")

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

    def calculate_atr(self, data, period=14):
        """Calculate Average True Range for volatility measurement"""
        try:
            high = data['High']
            low = data['Low']
            close = data['Close']
            
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=period).mean()
            
            return atr
        except Exception as e:
            print(f"❌ Error calculating ATR: {e}")
            return pd.Series()

    def get_market_condition(self, symbol, data):
        """Determine market condition for dynamic R:R"""
        try:
            # Calculate ATR for volatility
            atr = self.calculate_atr(data, 14)
            if atr.empty:
                return "NORMAL", 2.5
            
            current_atr = atr.iloc[-1]
            avg_atr = atr.mean()
            
            # Calculate trend strength
            ema_20 = data['Close'].ewm(span=20).mean()
            trend_strength = abs(data['Close'].iloc[-1] - ema_20.iloc[-1]) / ema_20.iloc[-1]
            
            # Determine condition and target R:R
            if current_atr > avg_atr * 1.5 and trend_strength > 0.02:
                return "HIGH_VOLATILITY", 4.0  # 4:1 R:R
            elif current_atr > avg_atr * 1.2 and trend_strength > 0.015:
                return "TRENDING", 3.0  # 3:1 R:R
            elif current_atr > avg_atr * 0.8:
                return "NORMAL", 2.5  # 2.5:1 R:R
            else:
                return "WEAK", 2.0  # 2:1 R:R
                
        except Exception as e:
            print(f"❌ Error determining market condition: {e}")
            return "NORMAL", 2.5

    def enhanced_volume_analysis(self, symbol, data):
        """Enhanced volume analysis for better entries"""
        try:
            current_volume = data['Volume'].iloc[-1]
            avg_volume_20 = data['Volume'].tail(20).mean()
            avg_volume_50 = data['Volume'].tail(50).mean()
            
            # Volume surge detection
            volume_surge = current_volume / avg_volume_20 if avg_volume_20 > 0 else 1
            
            # Volume trend
            volume_trend = data['Volume'].tail(5).mean() / data['Volume'].tail(20).mean() if data['Volume'].tail(20).mean() > 0 else 1
            
            return {
                'volume_surge': volume_surge,
                'volume_trend': volume_trend,
                'is_strong_volume': volume_surge >= 2.0 and volume_trend >= 1.2,
                'avg_volume_20': avg_volume_20,
                'current_volume': current_volume
            }
        except Exception as e:
            print(f"❌ Error in volume analysis: {e}")
            return {
                'volume_surge': 1,
                'volume_trend': 1,
                'is_strong_volume': False,
                'avg_volume_20': 0,
                'current_volume': 0
            }

    def get_higher_timeframe_bias(self, symbol):
        """Get 15-minute and 1-hour bias for confirmation"""
        try:
            # 15-minute data for trend confirmation
            data_15m = self.get_stock_data(symbol, period="2d", interval="15m")
            data_1h = self.get_stock_data(symbol, period="5d", interval="1h")
            
            if data_15m is None or data_1h is None or data_15m.empty or data_1h.empty:
                return {
                    'bias_15m': 'NEUTRAL',
                    'bias_1h': 'NEUTRAL',
                    'aligned': False
                }
            
            # Calculate EMAs
            ema_20_15m = data_15m['Close'].ewm(span=20).mean()
            ema_20_1h = data_1h['Close'].ewm(span=20).mean()
            
            current_price = data_15m['Close'].iloc[-1]
            
            bias_15m = "BULLISH" if current_price > ema_20_15m.iloc[-1] else "BEARISH"
            bias_1h = "BULLISH" if current_price > ema_20_1h.iloc[-1] else "BEARISH"
            
            return {
                'bias_15m': bias_15m,
                'bias_1h': bias_1h,
                'aligned': bias_15m == bias_1h
            }
        except Exception as e:
            print(f"❌ Error getting higher timeframe bias: {e}")
            return {
                'bias_15m': 'NEUTRAL',
                'bias_1h': 'NEUTRAL',
                'aligned': False
            }

    def get_optimal_trading_sessions(self):
        """Get optimal sessions for Dubai-based trader"""
        try:
            dubai_time = datetime.now(self.dubai_tz)
            
            # UK Session: 8:00 AM - 4:30 PM GMT (12:00 PM - 8:30 PM Dubai)
            uk_open = dubai_time.replace(hour=12, minute=0, second=0, microsecond=0)
            uk_close = dubai_time.replace(hour=20, minute=30, second=0, microsecond=0)
            
            # US Session: 9:30 AM - 4:00 PM EST (6:30 PM - 1:00 AM Dubai next day)
            us_open = dubai_time.replace(hour=18, minute=30, second=0, microsecond=0)
            us_close = dubai_time.replace(hour=1, minute=0, second=0, microsecond=0)
            
            # Handle US session crossing midnight
            if dubai_time.hour >= 18 or dubai_time.hour <= 1:
                us_session_active = True
            else:
                us_session_active = False
            
            return {
                'uk_session': uk_open <= dubai_time <= uk_close,
                'us_session': us_session_active,
                'dubai_time': dubai_time.strftime('%H:%M:%S')
            }
        except Exception as e:
            print(f"❌ Error getting trading sessions: {e}")
            return {
                'uk_session': False,
                'us_session': False,
                'dubai_time': '00:00:00'
            }

    def get_active_stocks_for_session(self):
        """Get stocks active in current session"""
        sessions = self.get_optimal_trading_sessions()
        
        if sessions['uk_session'] and sessions['us_session']:
            return self.all_stocks  # Both sessions active
        elif sessions['uk_session']:
            return self.uk_stocks  # UK session only
        elif sessions['us_session']:
            return self.us_stocks  # US session only
        else:
            return []  # No active session

    def is_market_open(self, symbol):
        """Check if market is open for specific symbol"""
        sessions = self.get_optimal_trading_sessions()
        
        if symbol in self.uk_stocks:
            return sessions['uk_session'], "UK market"
        elif symbol in self.us_stocks:
            return sessions['us_session'], "US market"
        else:
            return False, "Unknown market"

    def is_opening_range_period(self, symbol):
        """Check if we're in the opening range period"""
        try:
            dubai_time = datetime.now(self.dubai_tz)
            
            if symbol in self.uk_stocks:
                # UK opening: 8:00 AM - 8:30 AM GMT (12:00 PM - 12:30 PM Dubai)
                opening_start = dubai_time.replace(hour=12, minute=0, second=0, microsecond=0)
                opening_end = dubai_time.replace(hour=12, minute=30, second=0, microsecond=0)
            else:
                # US opening: 9:30 AM - 10:00 AM EST (6:30 PM - 7:00 PM Dubai)
                opening_start = dubai_time.replace(hour=18, minute=30, second=0, microsecond=0)
                opening_end = dubai_time.replace(hour=19, minute=0, second=0, microsecond=0)
            
            return opening_start <= dubai_time <= opening_end
        except Exception as e:
            print(f"❌ Error checking opening range period: {e}")
            return False

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
            volume_avg = data['Volume'].tail(20).mean() if len(data) >= 20 else data['Volume'].mean()
            
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

    def enhanced_entry_conditions(self, symbol, current_price, current_volume):
        """Enhanced entry conditions with multiple confirmations"""
        try:
            # Get current data for analysis
            data = self.get_stock_data(symbol, period="1d", interval="5m")
            if data is None or data.empty:
                return None, "No data available"
            
            # Get market condition
            market_condition, target_rr = self.get_market_condition(symbol, data)
            
            # Get volume analysis
            volume_analysis = self.enhanced_volume_analysis(symbol, data)
            
            # Get higher timeframe bias
            bias_analysis = self.get_higher_timeframe_bias(symbol)
            
            # Check basic breakout
            if symbol not in self.opening_ranges:
                return None, "No opening range data"
            
            orb = self.opening_ranges[symbol]
            orh = orb['orh']
            orl = orb['orl']
            
            # Determine breakout direction
            breakout_direction = None
            if current_price > orh:
                breakout_direction = 'LONG'
            elif current_price < orl:
                breakout_direction = 'SHORT'
            else:
                return None, "No breakout detected"
            
            # Enhanced confirmation requirements
            confirmations = {
                'volume_strong': volume_analysis['is_strong_volume'],
                'bias_aligned': bias_analysis['aligned'],
                'market_suitable': market_condition in ['NORMAL', 'TRENDING', 'HIGH_VOLATILITY'],
                'volume_surge': volume_analysis['volume_surge'] >= 1.5
            }
            
            # Require at least 3 out of 4 confirmations
            confirmation_count = sum(confirmations.values())
            
            if confirmation_count >= 3:
                # Calculate enhanced targets based on market condition
                if breakout_direction == 'LONG':
                    entry_price = orh + 0.05
                    stop_loss = orl - 0.10
                    risk_distance = entry_price - stop_loss
                    
                    target1 = entry_price + (target_rr * risk_distance)
                    target2 = entry_price + ((target_rr + 1) * risk_distance)
                    target3 = entry_price + (2 * orb['range_size'])
                    
                else:  # SHORT
                    entry_price = orl - 0.05
                    stop_loss = orh + 0.10
                    risk_distance = stop_loss - entry_price
                    
                    target1 = entry_price - (target_rr * risk_distance)
                    target2 = entry_price - ((target_rr + 1) * risk_distance)
                    target3 = entry_price - (2 * orb['range_size'])
                
                return {
                    'direction': breakout_direction,
                    'entry_price': entry_price,
                    'stop_loss': stop_loss,
                    'target1': target1,
                    'target2': target2,
                    'target3': target3,
                    'target_rr': target_rr,
                    'market_condition': market_condition,
                    'confirmations': confirmations,
                    'volume_analysis': volume_analysis,
                    'bias_analysis': bias_analysis
                }, f"Enhanced entry confirmed: {market_condition} market, {target_rr}:1 R:R"
            
            return None, f"Entry conditions not met ({confirmation_count}/4 confirmations)"
            
        except Exception as e:
            print(f"❌ Error in enhanced entry conditions: {e}")
            return None, str(e)

    def calculate_position_size(self, entry_price, stop_loss, market_condition):
        """Calculate position size based on risk management and market condition"""
        try:
            risk_per_share = abs(entry_price - stop_loss)
            if risk_per_share <= 0:
                return 0
            
            # Adjust risk based on market condition
            risk_multiplier = {
                'WEAK': 0.5,      # Reduce position in weak markets
                'NORMAL': 1.0,    # Standard position
                'TRENDING': 1.2,  # Slightly increase in trending markets
                'HIGH_VOLATILITY': 0.8  # Reduce in high volatility
            }.get(market_condition, 1.0)
            
            risk_amount = self.account_size * self.risk_per_trade * risk_multiplier
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
        """Execute a trade based on enhanced ORB strategy"""
        try:
            # Check daily limits
            if self.daily_stats['trades_today'] >= self.max_trades_per_day:
                return False, "Daily trade limit reached"
            
            if abs(self.daily_stats['daily_pnl']) >= (self.account_size * self.max_daily_loss):
                return False, "Daily loss limit reached"
            
            # Calculate position size
            position_size = self.calculate_position_size(
                trade_data['entry_price'], 
                trade_data['stop_loss'],
                trade_data['market_condition']
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
                'target_rr': trade_data['target_rr'],
                'market_condition': trade_data['market_condition'],
                'position_size': position_size,
                'risk_amount': position_size * abs(trade_data['entry_price'] - trade_data['stop_loss']),
                'timestamp': datetime.now().isoformat(),
                'status': 'ACTIVE',
                'tp1_hit': False,
                'tp2_hit': False,
                'current_stop': trade_data['stop_loss'],
                'confirmations': trade_data['confirmations'],
                'volume_analysis': trade_data['volume_analysis'],
                'bias_analysis': trade_data['bias_analysis']
            }
            
            # Add to active trades
            self.active_trades[trade['id']] = trade
            
            # Update daily stats
            self.daily_stats['trades_today'] += 1
            
            # Send enhanced Telegram notification
            confirmations_text = "\n".join([f"✅ {k}: {v}" for k, v in trade_data['confirmations'].items()])
            
            message = f"""
🚀 <b>Enhanced ORB Trade Executed</b>

📊 <b>Symbol:</b> {symbol}
📈 <b>Direction:</b> {trade_data['direction']}
💰 <b>Entry:</b> ${trade_data['entry_price']:.2f}
🛑 <b>Stop Loss:</b> ${trade_data['stop_loss']:.2f}
🎯 <b>Target 1:</b> ${trade_data['target1']:.2f} ({trade_data['target_rr']:.1f}:1 RR)
🎯 <b>Target 2:</b> ${trade_data['target2']:.2f} ({trade_data['target_rr']+1:.1f}:1 RR)
🎯 <b>Target 3:</b> ${trade_data['target3']:.2f}
📦 <b>Position Size:</b> {position_size} shares
💵 <b>Risk Amount:</b> ${trade['risk_amount']:.2f}
📊 <b>Market Condition:</b> {trade_data['market_condition']}
📈 <b>Volume Surge:</b> {trade_data['volume_analysis']['volume_surge']:.1f}x
📊 <b>Bias Alignment:</b> {trade_data['bias_analysis']['aligned']}

<b>Confirmations:</b>
{confirmations_text}

⏰ <b>Time:</b> {datetime.now().strftime('%H:%M:%S')}
            """
            
            self.send_telegram_message(message)
            
            # Save data
            self.save_trades_data()
            
            return True, f"Enhanced trade executed: {trade['id']}"
            
        except Exception as e:
            print(f"❌ Error executing trade: {e}")
            return False, str(e)

    def monitor_active_trades(self):
        """Monitor and manage active trades with enhanced logic"""
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
                
                # Check take profit targets with enhanced logic
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
                
                # Enhanced trailing stop after TP1
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
        """Handle take profit hit with enhanced notifications"""
        try:
            trade = self.active_trades[trade_id]
            
            if tp_level == 1:
                trade['tp1_hit'] = True
                # Close 50% of position
                trade['position_size'] = int(trade['position_size'] * 0.5)
                message = f"""
🎯 <b>Target 1 Hit!</b>

📊 <b>Symbol:</b> {trade['symbol']}
💰 <b>Price:</b> ${price:.2f}
📦 <b>Action:</b> 50% position closed
🎯 <b>R:R Achieved:</b> {trade['target_rr']:.1f}:1
📊 <b>Market Condition:</b> {trade['market_condition']}
⏰ <b>Time:</b> {datetime.now().strftime('%H:%M:%S')}
                """
            elif tp_level == 2:
                trade['tp2_hit'] = True
                # Close 25% more (75% total closed)
                trade['position_size'] = int(trade['position_size'] * 0.25)
                message = f"""
🎯 <b>Target 2 Hit!</b>

📊 <b>Symbol:</b> {trade['symbol']}
💰 <b>Price:</b> ${price:.2f}
📦 <b>Action:</b> 75% position closed
🎯 <b>R:R Achieved:</b> {trade['target_rr']+1:.1f}:1
📊 <b>Market Condition:</b> {trade['market_condition']}
⏰ <b>Time:</b> {datetime.now().strftime('%H:%M:%S')}
                """
            
            self.send_telegram_message(message)
            self.save_trades_data()
            
        except Exception as e:
            print(f"❌ Error handling take profit: {e}")

    def close_trade(self, trade_id, exit_price, reason):
        """Close a trade with enhanced tracking"""
        try:
            trade = self.active_trades[trade_id]
            
            # Calculate P&L
            if trade['direction'] == 'LONG':
                pnl = (exit_price - trade['entry_price']) * trade['position_size']
            else:
                pnl = (trade['entry_price'] - exit_price) * trade['position_size']
            
            # Calculate actual R:R achieved
            risk_amount = abs(trade['entry_price'] - trade['stop_loss']) * trade['position_size']
            actual_rr = pnl / risk_amount if risk_amount > 0 else 0
            
            # Update trade record
            trade['exit_price'] = exit_price
            trade['exit_reason'] = reason
            trade['pnl'] = pnl
            trade['actual_rr'] = actual_rr
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
            
            # Calculate win rate
            total_trades = len(self.trades_history)
            winning_trades = len([t for t in self.trades_history if t['pnl'] > 0])
            self.daily_stats['win_rate'] = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            
            # Calculate average R:R
            total_rr = sum([t.get('actual_rr', 0) for t in self.trades_history])
            self.daily_stats['avg_rr_achieved'] = total_rr / total_trades if total_trades > 0 else 0
            
            # Send enhanced notification
            pnl_emoji = "💰" if pnl > 0 else "📉"
            rr_emoji = "🎯" if actual_rr >= trade['target_rr'] else "⚠️"
            
            message = f"""
{pnl_emoji} <b>Enhanced Trade Closed</b>

📊 <b>Symbol:</b> {trade['symbol']}
📈 <b>Direction:</b> {trade['direction']}
💰 <b>Entry:</b> ${trade['entry_price']:.2f}
💵 <b>Exit:</b> ${exit_price:.2f}
📦 <b>Shares:</b> {trade['position_size']}
💸 <b>P&L:</b> ${pnl:.2f}
{rr_emoji} <b>R:R Achieved:</b> {actual_rr:.1f}:1 (Target: {trade['target_rr']:.1f}:1)
📊 <b>Market Condition:</b> {trade['market_condition']}
📝 <b>Reason:</b> {reason}
📈 <b>Win Rate:</b> {self.daily_stats['win_rate']:.1f}%
📊 <b>Avg R:R:</b> {self.daily_stats['avg_rr_achieved']:.1f}:1
⏰ <b>Time:</b> {datetime.now().strftime('%H:%M:%S')}
            """
            
            self.send_telegram_message(message)
            self.save_trades_data()
            
        except Exception as e:
            print(f"❌ Error closing trade: {e}")

    def run(self):
        """Main bot loop with enhanced session management"""
        print("🚀 Enhanced ORB Stock Trading Bot started")
        
        # Send startup message
        sessions = self.get_optimal_trading_sessions()
        startup_message = f"""
🚀 <b>Enhanced ORB Stock Trading Bot Started</b>

📈 <b>Strategy:</b> Opening Range Breakout (Enhanced)
🇺🇸 <b>US Stocks:</b> {len(self.us_stocks)} pairs
🇬🇧 <b>UK Stocks:</b> {len(self.uk_stocks)} pairs
📊 <b>Total Stocks:</b> {len(self.all_stocks)} pairs
🎯 <b>R:R Range:</b> 2:1 to 5:1 (Dynamic)
📍 <b>Location:</b> Dubai Timezone Optimized

<b>Current Sessions:</b>
🇬🇧 UK Market: {'✅ Open' if sessions['uk_session'] else '❌ Closed'}
🇺🇸 US Market: {'✅ Open' if sessions['us_session'] else '❌ Closed'}
🕐 <b>Dubai Time:</b> {sessions['dubai_time']}

⏰ <b>Started:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        self.send_telegram_message(startup_message)
        
        last_opening_range_calc = None
        
        while True:
            try:
                # Get current session info
                sessions = self.get_optimal_trading_sessions()
                active_stocks = self.get_active_stocks_for_session()
                
                if not active_stocks:
                    print("⏰ No active trading sessions")
                    time.sleep(300)  # Check every 5 minutes when no sessions
                    continue
                
                print(f"📊 Active stocks: {len(active_stocks)} ({'UK' if sessions['uk_session'] else ''}{'US' if sessions['us_session'] else ''})")
                
                # Calculate opening ranges during opening period
                for symbol in active_stocks:
                    if self.is_opening_range_period(symbol):
                        if last_opening_range_calc != datetime.now().date():
                            print(f"📊 Calculating opening range for {symbol}...")
                            self.calculate_opening_range(symbol)
                        last_opening_range_calc = datetime.now().date()
                
                # Monitor active trades
                if self.active_trades:
                    self.monitor_active_trades()
                
                # Check for new breakouts (only after opening range period)
                for symbol in active_stocks:
                    if symbol in self.opening_ranges:
                        # Check if market is open for this symbol
                        is_open, market_name = self.is_market_open(symbol)
                        if not is_open:
                            continue
                        
                        # Get current data
                        data = self.get_stock_data(symbol, period="1d", interval="1m")
                        if data is None or data.empty:
                            continue
                        
                        current_price = float(data['Close'].iloc[-1])
                        current_volume = float(data['Volume'].iloc[-1])
                        
                        # Check for enhanced breakout
                        breakout_data, message = self.enhanced_entry_conditions(
                            symbol, current_price, current_volume
                        )
                        
                        if breakout_data:
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
                dubai_time = datetime.now(self.dubai_tz)
                if (dubai_time.hour == 20 and dubai_time.minute >= 45) or (dubai_time.hour == 1 and dubai_time.minute >= 0):
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
    bot = EnhancedORBStockTradingBot()
    bot.run()
