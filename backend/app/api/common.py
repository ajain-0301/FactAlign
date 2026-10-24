import csv
import io
import json

from fastapi import Response


def csv_response(rows: list[dict], filename: str) -> Response:
    buf = io.StringIO()
    if rows:
        w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    # BOM so Excel on Windows opens Hindi text correctly
    return Response(("\ufeff" + buf.getvalue()).encode("utf-8"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def json_response(data, filename: str) -> Response:
    return Response(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})
