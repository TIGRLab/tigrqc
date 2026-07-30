"""Tests for parsers for various accepted ID formats.
"""

VALID_DATMAN_IDS = [
    'STU01_SIT_00000999_01_01',
    'STU01_SI1_PHA_FBN220101',
    'STU01_SI1_SI10001_01_02',
    'STUDY_SITE_001_02_01',
    'STU01_SIT_PILOT001_01_01',
    'STU01_SIT_STUDY001_02_03',
]


VALID_KCNI_IDS = [
    'STU01_SIT_0000_00_SE00_MR',
    'STU01_SIT_00000000_00_SE00_MR',
    'STU01_SIT_0000_01_SE01_EEG',
    'STU01_SIT_00000001_99_SE03_MR',
    'STU01_ABC_ADNPHA_20260101_MR',
]

VALID_BIDS_IDS = [
    ''
]

INVALID_DATMAN_IDS = [
    '',
    'abcdefgh',
    '12345678',
    'SITE_0001_01_01',                      # Missing study code
    'TES01_0001_01_01',                     # Missing site code
    'TES01_SITE_01_01',                     # Missing sub id
    'TES01_SITE_0001_01',                   # Missing session or timepoint
    'TES01_SITE_0001',                      # Missing both session + timepoint
    'tes01_site_0001',                      # Wrong case
    'TES01_SITE_PHA_000001_01',             # Phantom with a timepoint...
]

INVALID_KCNI_IDS = [
    '',
    'abcdefgh',
    '12345678',
    'SIT_0000_00_SE00_MR',                  # Missing Study code
    'STU01_0000_00_SE00_MR',                # Missing Site code
    'STU01_SIT_00_SE00_MR',                 # Missing sub ID
    'STU01_SIT_0000_SE00_MR',               # Missing timepoint
    'STU01_SIT_0000_00_MR',                 # Missing session
    'STU01_SIT_0000_00_00',                 # Missing modality
    'STU01_SIT_0000_00_00_MR',              # Missing 'SE' marker on session
    'STU01_SIT_0000_SE00_00_MR',            # Reversed timepoint and session
    'STUDY_SIT_0000_00_SE00_MR',            # Invalid study code format
    'STU01_SITE_0000_00_SE00_MR',           # Invalid site code format
    'STU01_SIT_123456789_00_SE00_MR',       # sub id too long
    'STU01_SIT_123_00_SE00_MR',             # sub id too short
    'STU01_SIT_1234_ABC_SE00_MR',           # Invalid timepoint
    'STU01_SIT_1234_999_SE01_MR',           # timepoint too long
    'STU01_SIT_1234_9_SE01_MR',             # timepoint too short
    'STU01_SIT_1234_00_SEABC_MR',           # invalid session
    'STU01_SIT_1234_00_SE1_MR',             # session too short
    'STU01_SIT_1234_00_SE999_MR',           # session too long
    'STU01_SIT_1234_00_SE00_999',           # Invalid modality field
    'STU01_SIT_1234_00_SE00_ABCDEFGH',      # Modality field too long
    'STU01_SIT_1234_00_SE00_M',             # Modality field too short
    'STU01-SIT-1234-00-SE00-MR',            # Invalid ID field delimiter
    'stu01_sit_1234_00_SE00_MR',            # invalid case
    'ST%01_S$T_1234_00_SE00_MR',            # invalid characters
    'STU01_SIT_ADNI_12345678',              # Phantom missing 'PHA' tag
    'STU01_SIT_PHA_12345678',               # Phantom missing 'type' code
]


# Bids test case needed to confirm subid override can let a study ID in too
# patterns = {'subid': '(?P<study>[A-Z]{3}[0-9]{2})(?P<site>[A-Z]{3})(?P<id>[A-Z0-9]+)'
# bc = BidsConvention(patterns=patterns)
# Then CLM01UTO00001 etc. should work.


# Need tests for:
#   -> Basic ID parsing
#   -> pattern overrides
#   -> Field validation (study and/or site) or none at all
