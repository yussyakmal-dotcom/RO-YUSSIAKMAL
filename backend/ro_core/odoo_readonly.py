"""Strictly read-only Odoo 19 JSON-2 client.

Only whitelisted model/search_read calls are supported. It cannot perform
create/write/unlink/action methods, even if credentials have write permissions.
"""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


class OdooReadError(RuntimeError):
    pass


class OdooReadOnlyClient:
    ALLOWED_MODELS = frozenset({
        "stock.warehouse",
        "stock.location",
        "product.product",
        "mrp.bom",
        "mrp.bom.line",
    })

    def __init__(self, base_url, api_key, database="", timeout=30):
        url = (base_url or "").strip().rstrip("/")
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or not parsed.hostname or
                parsed.username or parsed.password or parsed.query or
                parsed.fragment or parsed.path not in ("", "/")):
            raise OdooReadError(
                "ODOO_BASE_URL harus berupa root HTTPS, contoh https://company.odoo.com"
            )
        if not api_key or api_key.startswith("CHANGE_ME"):
            raise OdooReadError("ODOO_API_KEY belum diatur pada .env")
        self.base_url = url
        self.api_key = api_key.strip()
        self.database = (database or "").strip()
        self.timeout = timeout

    @classmethod
    def from_env(cls):
        return cls(
            base_url=os.getenv("ODOO_BASE_URL", ""),
            api_key=os.getenv("ODOO_API_KEY", ""),
            database=os.getenv("ODOO_DATABASE", ""),
        )

    def search_read(self, model, fields, domain=None, limit=200, offset=0):
        if model not in self.ALLOWED_MODELS:
            raise OdooReadError("Model Odoo tidak diizinkan untuk connector read-only")
        if not isinstance(fields, (list, tuple)) or not fields:
            raise ValueError("fields wajib berupa daftar field eksplisit")
        if not 1 <= limit <= 500 or offset < 0:
            raise ValueError("Pagination di luar batas")
        payload = json.dumps({
            "context": {"lang": "en_US"},
            "domain": domain if domain is not None else [],
            "fields": list(fields),
            "limit": limit,
            "offset": offset,
            "order": "id",
        }).encode("utf-8")
        headers = {
            "Authorization": f"bearer {self.api_key}",
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "ro-middleware-readonly/0.1",
        }
        if self.database:
            headers["X-Odoo-Database"] = self.database
        request = Request(
            f"{self.base_url}/json/2/{model}/search_read",
            data=payload,
            method="POST",
            headers=headers,
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                data = json.load(response)
        except HTTPError as exc:
            # Never echo Odoo response body: it may contain server traceback.
            raise OdooReadError(
                f"Odoo mengembalikan HTTP {exc.code} pada {model}/search_read; "
                "periksa izin API key dan field model di halaman /doc Odoo"
            ) from None
        except (URLError, TimeoutError, OSError) as exc:
            raise OdooReadError(
                f"Gagal menghubungi Odoo saat membaca {model} ({type(exc).__name__})"
            ) from None
        except (ValueError, UnicodeDecodeError):
            raise OdooReadError(
                f"Respons dari Odoo bukan JSON yang valid untuk {model}"
            ) from None
        if not isinstance(data, list):
            raise OdooReadError(
                f"Respons Odoo {model}/search_read harus berbentuk daftar"
            )
        return data

    def all_records(self, model, fields, domain=None, page_size=200, max_pages=250):
        """Yield pages; bounded to avoid accidental endless import."""
        for page in range(max_pages):
            rows = self.search_read(
                model, fields=fields, domain=domain,
                limit=page_size, offset=page * page_size,
            )
            yield from rows
            if len(rows) < page_size:
                return
        raise OdooReadError(f"Batas jumlah halaman tercapai saat membaca {model}")
