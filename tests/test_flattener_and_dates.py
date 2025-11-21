# tests/test_flattener_and_dates.py


def test_flattener_outputs_expected_columns(sample_flat_rows):
    # Basic flattener sanity: at least 3 rows (2 items + 1 unassigned)
    assert len(sample_flat_rows) >= 3

    row = sample_flat_rows[0]
    # Columns defined in config.XLSX_COLUMNS
    expected_keys = {
        "Unit",
        "Finding_Aid_Reference",
        "Series",
        "Series_Notes",
        "Title",
        "Text",
        "Dates",
        "Item_Annotations",
        "Hierarchy_Path",
    }
    assert expected_keys.issubset(row.keys())


def test_date_range_enrichment_adds_columns(sample_flat_rows):
    from finding_aids_ocr.post_processing.date_range import enrich_rows_with_date_ranges

    enriched = enrich_rows_with_date_ranges(sample_flat_rows)
    assert len(enriched) == len(sample_flat_rows)

    extra_keys = {
        "Dates_Sortable",
        "Date_Complete",
        "Start_Date",
        "End_Date",
        "Start_Date_Sortable",
        "End_Date_Sortable",
        "Start_Date_Complete",
        "End_Date_Complete",
    }
    assert extra_keys.issubset(enriched[0].keys())

    # Spot check behaviour: n.d. should be incomplete
    loose = [r for r in enriched if r["Title"] == "Loose material"][0]
    assert loose["Date_Complete"] == "incomplete"
