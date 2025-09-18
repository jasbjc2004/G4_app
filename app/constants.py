# Usage of testdata
READ_SAMPLE = False
BEAUTY_SPEED = True

NAME_APP = 'Bimanual Hand Movement'

# Lay-out of the PDF
TITLE_LETTER_SIZE = 13
SUBTITLE_LETTER_SIZE = 11
SUB_SUB_TITLE_LETTER_SIZE = 9
FONT_LETTER_SIZE = 8
LETTER_SIZE = 8

# All available (bright) colors for the events
COLORS = [
    ("#FF0000", "Red"),  # Pure red
    ("#00FF00", "Green"),  # Pure green
    ("#0000FF", "Blue"),  # Pure blue
    ("#FFFF00", "Yellow"),  # Pure yellow
    ("#FF00FF", "Magenta"),  # Pure magenta
    ("#00FFFF", "Cyan"),  # Pure cyan
    ("#FF8000", "Orange"),  # Orange
    ("#9932CC", "Purple"),  # Purple
    ("#000000", "Black"),  # For contrast on light backgrounds
    ("#FF0080", "Pink")  # Pink - distinct from red/magenta
]

# The name of all parameters (easier/ not need to copy all)
BIMAN_PARAMS = ['Total time (s)', 'Temporal coupling (/)', 'Movement overlap  (/)', 'Goal synchronization (/)']
UNIMAN_PARAMS = ['Time box hand (s)', 'Time 1e phase BH (s)', 'Time 2e phase BH (s)', 'Time trigger hand (s)',
                 'Smoothness BH (/)', 'Smoothness TH (/)', 'Path length BH (cm)', 'Path 1e phase BH (cm)',
                 'Path 2e phase BH (cm)', 'Path length TH (cm)']
