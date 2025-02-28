# -*- coding: utf-8 -*-
import datetime
import logging
import re
from collections import OrderedDict
from io import BytesIO, IOBase
from typing import List

import xlrd
from pyxform import xls2json
from pyxform.errors import PyXFormError
from pyxform.xls2json_backends import get_definition_data
from slugify import slugify
from xlwt import Workbook

from apollo.formsframework.models import Form
from apollo.utils import generate_identifier

gt_constraint_regex = re.compile(r"(?:.*\.\s*\>={0,1}\s*)(\d+)")
lt_constraint_regex = re.compile(r"(?:.*\.\s*\<={0,1}\s*)(\d+)")

logger = logging.getLogger(__name__)


def _make_form_instance(metadata):
    form = Form()
    form.name = metadata.get("name")
    form.prefix = metadata.get("prefix")
    form.form_type = metadata.get("form_type")
    form.accredited_voters_tag = metadata.get("accredited_voters_tag")
    form.blank_votes_tag = metadata.get("blank_votes_tag")
    form.invalid_votes_tag = metadata.get("invalid_votes_tag")
    form.registered_voters_tag = metadata.get("registered_voters_tag")
    vote_shares = metadata.get("vote_shares")
    if vote_shares is not None:
        form.vote_shares = sorted(vote_shares.split(","))
    turnout_fields = metadata.get("turnout_fields")
    if turnout_fields is not None:
        form.turnout_fields = sorted(turnout_fields.split(","))

    try:
        form.calculate_moe = bool(int(metadata.get("calculate_moe")))
    except ValueError:
        form.calculate_moe = False
    try:
        form.quality_checks_enabled = bool(int(metadata.get("quality_checks_enabled")))
    except ValueError:
        form.quality_checks_enabled = False
    try:
        form.require_exclamation = bool(int(metadata.get("require_exclamation")))
    except ValueError:
        form.require_exclamation = False

    return form


def _process_survey_worksheet(sheet_data, form_data):
    current_group = None
    for field_dict in sheet_data:
        if field_dict["type"] == "begin group":
            current_group = {"name": field_dict["label"], "slug": slugify(field_dict["name"]), "fields": []}
            form_data["groups"].append(current_group)
            continue

        if "name" not in field_dict:
            continue

        record_type = field_dict["type"]
        field = {"tag": field_dict["name"], "description": field_dict["label"], "analysis_type": "N/A"}

        # integer
        if record_type == "integer":
            field["type"] = record_type

            # add default constraints
            field["min"] = 0
            field["max"] = 9999

            # TODO: probably a better way to handle this than
            # use regexes
            constraint_text = field_dict.get("constraints")
            if constraint_text:
                gt_match = gt_constraint_regex.match(constraint_text)
                lt_match = lt_constraint_regex.match(constraint_text)
                if gt_match:
                    try:
                        field["min"] = int(gt_match.group(1))
                    except ValueError:
                        pass

                if lt_match:
                    try:
                        field["max"] = int(lt_match.group(1))
                    except ValueError:
                        pass

            # add expected value
            if field_dict.get("extra"):
                try:
                    field["expected"] = int(field_dict.get("extra"))
                except (TypeError, ValueError):
                    pass

        # legacy boolean
        elif record_type == "boolean":
            field["type"] = "integer"
            field["max"] = 1
            field["min"] = 0

        # text
        elif record_type == "text":
            if field_dict.get("extra") == "comment":
                field["type"] = "comment"
            else:
                field["type"] = "string"

        # boolean - legacy
        elif "boolean" in record_type:
            field["type"] = "integer"
            field["min"] = 0
            field["max"] = 1

        # single-choice
        elif record_type.startswith("select_one"):
            field["type"] = "select"

        # multiple-choice
        elif record_type.startswith("select"):
            field["type"] = "multiselect"
        elif record_type == "image":
            field["type"] = "image"
        else:
            continue

        current_group["fields"].append(field)
        form_data["field_cache"].update({field["tag"]: field})


def _process_choices_worksheet(choices_data, form_schema):
    for option_dict in choices_data:
        if option_dict["list name"] == "boolean":
            continue

        tag, _ = option_dict["list name"].split("_")
        field = form_schema["field_cache"][tag]
        if not field.get("options"):
            field["options"] = {}
        field["options"].update({option_dict["label"]: int(option_dict["name"])})


def _process_analysis_worksheet(analysis_data, form_schema):
    vote_shares = []
    for analysis_dict in analysis_data:
        field = form_schema["field_cache"][analysis_dict["name"]]
        analysis_type = analysis_dict["analysis"]

        # handle legacy cases
        if analysis_type == "PROCESS":
            if field["type"] == "integer":
                field["analysis_type"] = "mean"
            elif field["type"] in ("multiselect", "select"):
                field["analysis_type"] = "histogram"
            else:
                field["analysis_type"] = "N/A"
        elif analysis_type == "RESULT":
            vote_shares.append(field["tag"])
            field["analysis_type"] = "N/A"
        else:
            field["analysis_type"] = analysis_type

    return vote_shares


def _process_qa_worksheet(qa_data):
    quality_checks = []
    current_check = None
    current_name = None
    for qa_dict in qa_data:
        if "name" in qa_dict:
            if current_name != qa_dict["name"]:
                if current_check is not None:
                    quality_checks.append(current_check)
                current_name = qa_dict["name"]
                current_check = {"name": qa_dict["name"], "description": qa_dict["description"], "criteria": []}

            if qa_dict["left"] and qa_dict["relation"] and qa_dict["right"] and qa_dict["conjunction"]:
                current_check["criteria"].append(
                    {
                        "lvalue": qa_dict["left"],
                        "comparator": qa_dict["relation"],
                        "rvalue": qa_dict["right"],
                        "conjunction": qa_dict["conjunction"],
                    }
                )
                continue
        else:
            # process legacy import
            if qa_dict["description"] and qa_dict["left"] and qa_dict["relation"] and qa_dict["right"]:
                qa_check = {
                    "name": generate_identifier(),
                    "description": qa_dict["description"],
                    "lvalue": qa_dict["left"],
                    "comparator": qa_dict["relation"],
                    "rvalue": qa_dict["right"],
                }
                quality_checks.append(qa_check)

    if current_check is not None:
        quality_checks.append(current_check)

    return quality_checks


def format_cell_value(cell, datemode):
    """Format the cell value based on its type."""
    if cell.ctype == xlrd.XL_CELL_BOOLEAN:
        return "TRUE" if cell.value else "FALSE"
    elif cell.ctype == xlrd.XL_CELL_NUMBER:
        if int(cell.value) == cell.value:
            return str(int(cell.value))
        else:
            return str(cell.value)
    elif cell.ctype == xlrd.XL_CELL_DATE:
        datetime_or_time_only = xlrd.xldate_as_datetime(cell.value, datemode)
        if datetime_or_time_only[:3] == (0, 0, 0):
            return str(datetime.time(*datetime_or_time_only[3:]))
        return str(datetime.datetime(*datetime_or_time_only))
    else:
        return str(cell.value).replace(chr(160), " ")


def worksheet_to_dict(worksheet, datemode) -> List[OrderedDict]:
    """Converts a worksheet data into a list of dicts using the first row as the header."""
    columns = []
    records = []
    for row_ix in range(worksheet.nrows):
        if row_ix == 0:  # first row
            columns = [format_cell_value(column, datemode) for column in worksheet.row(0)]
        else:
            records.append(
                OrderedDict(
                    {
                        column_name: format_cell_value(worksheet.row(row_ix)[column_ix], datemode)
                        for column_ix, column_name in enumerate(columns)
                    }
                )
            )
    return records


def import_form(sourcefile: bytes | BytesIO | IOBase):
    """Import the form schema."""
    try:
        file_data = xls2json.xls_to_dict(sourcefile)
    except PyXFormError:
        logger.exception("Error parsing Excel schema file")
        raise

    # TODO: This is hacky, very fragile and likely to break. We either completely
    # breakaway from using pyxform or we find a way to get the library to parse all
    # the worksheets in the file.
    sourcefile.seek(0)  # reset the read pointer to the beginning of the file
    definition = get_definition_data(sourcefile)
    workbook = xlrd.open_workbook(file_contents=definition.data.getvalue())

    survey_data = file_data.get("survey")
    choices_data = file_data.get("choices")
    analysis_data = worksheet_to_dict(workbook.sheet_by_name("analysis"), workbook.datemode)
    metadata = worksheet_to_dict(workbook.sheet_by_name("metadata"), workbook.datemode)
    qa_data = worksheet_to_dict(workbook.sheet_by_name("quality_checks"), workbook.datemode)

    if not (survey_data and metadata):
        return

    form = _make_form_instance(metadata[0])
    form.data = {"groups": [], "field_cache": {}}

    # go over the survey worksheet
    _process_survey_worksheet(survey_data, form.data)

    # go over the options worksheet
    if choices_data:
        _process_choices_worksheet(choices_data, form.data)

    # go over the analysis worksheet
    if analysis_data:
        vote_shares = _process_analysis_worksheet(analysis_data, form.data)
        form.vote_shares = vote_shares

    # go over the quality checks
    if qa_data:
        form.quality_checks = _process_qa_worksheet(qa_data)

    # remove the field cache
    form.data.pop("field_cache")
    return form


def export_form(form):
    """Export the form schema."""
    book = Workbook()

    # set up worksheets
    survey_sheet = book.add_sheet("survey")
    choices_sheet = book.add_sheet("choices")
    analysis_sheet = book.add_sheet("analysis")
    metadata_sheet = book.add_sheet("metadata")

    if form.form_type == "CHECKLIST" and form.quality_checks_enabled:
        qa_sheet = book.add_sheet("quality_checks")
    else:
        qa_sheet = None

    # set up headers
    survey_header = ["type", "name", "label", "constraints", "extra"]
    choices_header = ["list name", "name", "label"]
    analysis_header = ["name", "analysis"]
    metadata_header = [
        "name",
        "prefix",
        "form_type",
        "require_exclamation",
        "calculate_moe",
        "accredited_voters_tag",
        "invalid_votes_tag",
        "registered_voters_tag",
        "blank_votes_tag",
        "quality_checks_enabled",
        "vote_shares",
        "turnout_fields",
    ]  # noqa
    qa_header = ["name", "description", "left", "relation", "right", "conjunction"]

    # output headers
    for col, value in enumerate(survey_header):
        survey_sheet.write(0, col, value)
    for col, value in enumerate(choices_header):
        choices_sheet.write(0, col, value)
    for col, value in enumerate(analysis_header):
        analysis_sheet.write(0, col, value)
    for col, value in enumerate(metadata_header):
        metadata_sheet.write(0, col, value)
    if qa_sheet:
        for col, value in enumerate(qa_header):
            qa_sheet.write(0, col, value)

    # fill out form properties
    metadata_sheet.write(1, 0, form.name)
    metadata_sheet.write(1, 1, form.prefix)
    metadata_sheet.write(1, 2, form.form_type.code)
    metadata_sheet.write(1, 3, 1 if form.require_exclamation else 0)
    metadata_sheet.write(1, 4, 1 if form.calculate_moe else 0)
    metadata_sheet.write(1, 5, form.accredited_voters_tag)
    metadata_sheet.write(1, 6, form.invalid_votes_tag)
    metadata_sheet.write(1, 7, form.registered_voters_tag)
    metadata_sheet.write(1, 8, form.blank_votes_tag)
    metadata_sheet.write(1, 9, 1 if form.quality_checks_enabled else 0)
    vote_shares = ",".join(form.vote_shares) if form.vote_shares else ""
    turnout_fields = ",".join(form.turnout_fields) if form.turnout_fields else ""
    metadata_sheet.write(1, 10, vote_shares)
    metadata_sheet.write(1, 11, turnout_fields)

    # write out form structure
    current_survey_row = 1
    current_choices_row = 1
    current_analysis_row = 1
    groups = form.data.get("groups")
    if groups and isinstance(groups, list):
        current_group = None
        for group in groups:
            if not group:
                continue

            if current_group:
                current_group = group
                survey_sheet.write(current_survey_row, 0, "end group")
                current_survey_row += 1
            survey_sheet.write(current_survey_row, 0, "begin group")
            survey_sheet.write(current_survey_row, 1, slugify(group["name"]))
            survey_sheet.write(current_survey_row, 2, group["name"])
            current_survey_row += 1
            current_group = group

            fields = group.get("fields")
            if fields and isinstance(fields, list):
                for field in fields:
                    # output the type
                    if field["type"] == "integer":
                        survey_sheet.write(current_survey_row, 0, "integer")
                        survey_sheet.write(
                            current_survey_row,
                            3,
                            ". >= {} and . <= {}".format(field.get("min", 0), field.get("max", 9999)),
                        )

                        # write out the expected/target value if it exists
                        # this assumes that 0 is not a valid value
                        if field.get("expected"):
                            survey_sheet.write(current_survey_row, 4, field["expected"])
                    elif field["type"] == "boolean":
                        survey_sheet.write(current_survey_row, 0, "integer")
                        survey_sheet.write(
                            current_survey_row,
                            3,
                            ". >= {} and . <= {}".format(field.get("min", 0), field.get("max", 1)),
                        )

                    elif field["type"] in ("comment", "string"):
                        survey_sheet.write(current_survey_row, 0, "text")
                        if field["type"] == "comment":
                            survey_sheet.write(current_survey_row, 4, "comment")
                    elif field["type"] == "image":
                        survey_sheet.write(current_survey_row, 0, field["type"])
                    else:
                        # for questions with choices, write them to the
                        # choices sheet
                        option_list_name = "{}_options".format(field["tag"])
                        options = field.get("options")
                        for description, value in options.items():
                            choices_sheet.write(current_choices_row, 0, option_list_name)
                            choices_sheet.write(current_choices_row, 1, value)
                            choices_sheet.write(current_choices_row, 2, description)
                            current_choices_row += 1

                        if field["type"] in ("category", "select"):
                            survey_sheet.write(current_survey_row, 0, "select_one {}".format(option_list_name))
                            if field.get("expected"):
                                survey_sheet.write(current_survey_row, 4, field["expected"])
                        else:
                            survey_sheet.write(current_survey_row, 0, "select_multiple {}".format(option_list_name))

                    # output the name and description
                    survey_sheet.write(current_survey_row, 1, field["tag"])
                    survey_sheet.write(current_survey_row, 2, field["description"])
                    current_survey_row += 1

                    # also output the analysis
                    analysis_sheet.write(current_analysis_row, 0, field["tag"])
                    analysis_sheet.write(current_analysis_row, 1, field["analysis_type"])
                    current_analysis_row += 1

        if current_group:
            survey_sheet.write(current_survey_row, 0, "end group")

    quality_checks = form.quality_checks
    if quality_checks and qa_sheet:
        row = 1
        for check in quality_checks:
            if "criteria" in check:
                for term in check["criteria"]:
                    qa_sheet.write(row, 0, check["name"])
                    qa_sheet.write(row, 1, check["description"])
                    qa_sheet.write(row, 2, term["lvalue"])
                    qa_sheet.write(row, 3, term["comparator"])
                    qa_sheet.write(row, 4, term["rvalue"])
                    qa_sheet.write(row, 5, term["conjunction"])
                    row += 1
            else:
                qa_sheet.write(row, 0, check["name"])
                qa_sheet.write(row, 1, check["description"])
                qa_sheet.write(row, 2, check["lvalue"])
                qa_sheet.write(row, 3, check["comparator"])
                qa_sheet.write(row, 4, check["rvalue"])
                qa_sheet.write(row, 5, "&&")
                row += 1

    return book
