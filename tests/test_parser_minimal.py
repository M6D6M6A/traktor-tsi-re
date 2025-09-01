from traktor_tsi.parser import TsiParser
from traktor_tsi.xml import extract_mapping_blob


def test_parse_smoke():
    # Put a tiny sample .tsi under examples/ to smoke-test decode + parse
    # (You can commit a trimmed TSI created via Traktor with 1-2 mappings.)
    try:
        blob = extract_mapping_blob("examples/sample.tsi")
    except FileNotFoundError:
        # allow running tests without example file
        return
    rows = TsiParser().parse(blob)
    assert isinstance(rows, list)
    # If a sample is present, at least ensure object-like rows
    if rows:
        r = rows[0]
        assert hasattr(r, "traktor_control_id")
