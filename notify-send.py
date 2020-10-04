import subprocess

while True:
    stdin = input()
    subprocess.call(["notify-send", stdin])

# let my_notif = jobstart("python notify-send.py")
# echo chansend(my_notif,"hey\n How are you\n")
# Notifications:
#       hey
#       How are you

# NOTE: in chansend, " " must be used, not ' '
# '\n' is literally \n, and not NewLine
# It does not trigger the input()

# Also, the query MUST have \n at last
# Otherwise the query will simply remain in the buffer, and not be executed

# Eg:
# echo chansend(my_notif,"hey\n How are you")
# echo chansend(my_notif,"hey\n How are you")
# Outputs:
#       hey
#       How are youhey
# See how the queryies are getting merged?
