"""Apply mutations to reference notes -> data/notes/<variant_id>.json."""
import _path  # noqa: F401
from jtj.mutate import load_cases, write_notes

print(f"wrote {write_notes(load_cases())} note variants")
