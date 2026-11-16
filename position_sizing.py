# bposition_sizing.py
def position_size(account_balance, risk_percent, entry_price, stop_loss_price):
    risk_amount = account_balance * (risk_percent/100.0)
    per_share_risk = abs(entry_price - stop_loss_price)
    if per_share_risk == 0:
        return 0
    qty = risk_amount / per_share_risk
    return int(qty)

if __name__ == "__main__":
 
    account = 10000.0  
    risk_pct = 1.0    
    entry = 150.0
    stop = 145.0
    qty = position_size(account, risk_pct, entry, stop)
    print(f"Account {account}, risk {risk_pct}% -> risk_amount {account*(risk_pct/100):.2f}")
    print(f"Per share risk {abs(entry-stop):.2f}, suggested qty = {qty}")
