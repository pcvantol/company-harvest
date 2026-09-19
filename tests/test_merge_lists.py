from pathlib import Path

import pytest
from openpyxl import Workbook

from company_lookup.audit import verify
from company_lookup.core import HarvestError, initialize_run, read_tsv
from company_lookup.merge_lists import InputOptions, _detect_delimiter, merge_lists


def _csv(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_merge_exclude_and_preference(tmp_path: Path) -> None:
    left = tmp_path / "left.tsv"
    right = tmp_path / "right.csv"
    _csv(left, "Bedrijfsnaam\tKVK-nummer\tsector\nAlpha B.V.\t01234567\tIT\nConflict A\t87654321\tA\n")
    _csv(right, "naam,kvkNummer,sector,actief\nAlpha B.V.,01234567,Tech,nee\nConflict B,87654321,B,ja\nBad,123,x,ja\n")
    run = initialize_run(tmp_path / "exclude", 1, "MERGE_LISTS")
    paths = merge_lists(run, left, right, "exclude")
    assert [row["KVK-nummer"] for row in read_tsv(paths[0])] == ["01234567"]
    assert len(read_tsv(paths[3])) == 2 and len(read_tsv(paths[4])) == 2 and len(read_tsv(paths[5])) == 1
    assert "UNCONFIRMED_IMPORTED" in paths[2].read_text()
    assert verify(run)["valid"]
    run2 = initialize_run(tmp_path / "prefer", 1, "MERGE_LISTS")
    preferred = merge_lists(run2, left, right, "prefer-left")
    assert len(read_tsv(preferred[0])) == 2


def test_merge_xlsx_and_ambiguity(tmp_path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Bedrijven"
    sheet.append(["naam", "kvkNummer", "extra"])
    sheet.append(["@Naam", 12345678, "x"])
    sheet.append(["Formula", "=1+1", "x"])
    xlsx = tmp_path / "input.xlsx"
    workbook.save(xlsx)
    csv_path = tmp_path / "other.csv"
    _csv(csv_path, "naam;kvkNummer\nBeta;23456789\n")
    run = initialize_run(tmp_path / "xlsx", 1, "MERGE_LISTS")
    paths = merge_lists(run, xlsx, csv_path, "exclude")
    assert len(read_tsv(paths[0])) == 2 and len(read_tsv(paths[5])) == 1
    assert _detect_delimiter("a;b\n1;2") == ";"
    with pytest.raises(HarvestError):
        _detect_delimiter("onecolumn")
    with pytest.raises(HarvestError):
        merge_lists(initialize_run(tmp_path / "badpolicy", 1, "MERGE_LISTS"), xlsx, csv_path, "bad")
    with pytest.raises(HarvestError):
        merge_lists(initialize_run(tmp_path / "badcolumn", 1, "MERGE_LISTS"), xlsx, csv_path, "exclude", InputOptions(name_column="missing"))


def test_csv_embedded_newline(tmp_path: Path) -> None:
    left = tmp_path / "left.csv"
    right = tmp_path / "right.csv"
    _csv(left, 'naam,kvkNummer,notitie\n"Alpha\nB.V.",12345678,"regel\ntwee"\n')
    _csv(right, "naam,kvkNummer\nBeta,23456789\n")
    run = initialize_run(tmp_path / "multi", 1, "MERGE_LISTS")
    paths = merge_lists(run, left, right, "exclude")
    assert len(read_tsv(paths[0])) == 2


def test_preferred_side_internal_conflict(tmp_path: Path) -> None:
    left = tmp_path / "l.csv"; right = tmp_path / "r.csv"
    _csv(left, "naam,kvkNummer\nA,12345678\nB,12345678\n")
    _csv(right, "naam,kvkNummer\nC,12345678\n")
    run = initialize_run(tmp_path / "run", 1, "MERGE_LISTS")
    paths = merge_lists(run, left, right, "prefer-left")
    assert read_tsv(paths[0]) == []
    assert {row["reason"] for row in read_tsv(paths[3])} == {"UNRESOLVED_WITHIN_PREFERRED_SOURCE"}
