# Mission 4: a legitimate flow. Send Bob the speaker contracts.
# Why is this allowed without asking anyone? Then change the recipient to the
# director, and then to guest@unknown.example. Predict each result first.
doc = read_file("speaker-contracts.pdf")
send_email(to="bob@partner.example", subject="Contracts", body="Attached.", attachment=doc)
