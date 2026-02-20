"""
Procreate File Reader
=====================
Reads and parses .procreate files (which are ZIP archives).
Supports Procreate 4.x and 5.x formats.

.procreate files contain:
  - QuickLook/Thumbnail.png  -> Preview thumbnail
  - Document.archive         -> Binary plist with document metadata
  - Layer data in numbered directories

Author: ProcreateViewer (Open Source)
License: MIT
"""

import zipfile
import plistlib
import struct
import io
import os
from typing import Optional, List, Dict, Any

from PIL import Image


class ProcreateLayer:
    """Represents a single layer in a Procreate document."""

    def __init__(
        self,
        name: str = "Untitled",
        uuid: str = "",
        opacity: float = 1.0,
        visible: bool = True,
        blend_mode: int = 0,
    ):
        self.name = name
        self.uuid = uuid
        self.opacity = opacity
        self.visible = visible
        self.blend_mode = blend_mode
        self.thumbnail: Optional[Image.Image] = None

    def __repr__(self):
        vis = "visible" if self.visible else "hidden"
        return f"ProcreateLayer('{self.name}', {vis}, opacity={self.opacity:.0%})"


class ProcreateFile:
    """
    Parser for .procreate files.

    Usage:
        with ProcreateFile('artwork.procreate') as pf:
            pf.thumbnail.show()
            print(f"Canvas: {pf.canvas_width}x{pf.canvas_height}")
            for layer in pf.layers:
                print(layer)
    """

    BLEND_MODES = {
        0: "Normal",
        1: "Multiply",
        2: "Screen",
        3: "Overlay",
        4: "Darken",
        5: "Lighten",
        6: "Color Dodge",
        7: "Color Burn",
        8: "Soft Light",
        9: "Hard Light",
        10: "Difference",
        11: "Exclusion",
        12: "Hue",
        13: "Saturation",
        14: "Color",
        15: "Luminosity",
        16: "Add",
        17: "Linear Burn",
        18: "Vivid Light",
        19: "Linear Light",
        20: "Pin Light",
        21: "Hard Mix",
        22: "Subtract",
        23: "Divide",
    }

    def __init__(self, filepath: str):
        self.filepath = os.path.abspath(filepath)
        self.filename = os.path.basename(filepath)
        self.thumbnail: Optional[Image.Image] = None
        self.composite: Optional[Image.Image] = None
        self.layers: List[ProcreateLayer] = []
        self.canvas_width: int = 0
        self.canvas_height: int = 0
        self.dpi: int = 132
        self.orientation: int = 0
        self.color_profile: str = "sRGB"
        self.layer_count: int = 0
        self.video_enabled: bool = False
        self.metadata: Dict[str, Any] = {}
        self._zip: Optional[zipfile.ZipFile] = None
        self._document_archive: Optional[Dict] = None
        self._archive_objects: List[Any] = []
        self._load()

    # ── Loading ────────────────────────────────────────────────────────

    def _load(self):
        """Load and parse the .procreate file."""
        if not os.path.isfile(self.filepath):
            raise FileNotFoundError(f"File not found: {self.filepath}")

        if not zipfile.is_zipfile(self.filepath):
            raise ValueError(f"Not a valid .procreate file (not a ZIP): {self.filepath}")

        self._zip = zipfile.ZipFile(self.filepath, "r")
        self._load_thumbnail()
        self._load_composite()
        self._load_document_archive()
        self._parse_metadata()
        self._parse_layers()

    # ── Thumbnail ──────────────────────────────────────────────────────

    def _load_thumbnail(self):
        """Extract the QuickLook thumbnail."""
        candidates = [
            "QuickLook/Thumbnail.png",
            "QuickLook/thumbnail.png",
            "Thumbnail.png",
        ]
        for path in candidates:
            img = self._try_load_image(path)
            if img:
                self.thumbnail = img
                return

        # Fallback: any PNG in QuickLook/
        for name in self._zip.namelist():
            if name.startswith("QuickLook/") and name.lower().endswith(".png"):
                img = self._try_load_image(name)
                if img:
                    self.thumbnail = img
                    return

    def _load_composite(self):
        """Try to load the composite / flattened preview."""
        candidates = [
            "QuickLook/Preview.png",
            "QuickLook/preview.png",
            "composite.png",
        ]
        for path in candidates:
            img = self._try_load_image(path)
            if img:
                self.composite = img
                return

    def _try_load_image(self, zip_path: str) -> Optional[Image.Image]:
        """Attempt to load an image from the ZIP archive."""
        try:
            with self._zip.open(zip_path) as f:
                img = Image.open(io.BytesIO(f.read()))
                img.load()
                return img
        except (KeyError, Exception):
            return None

    # ── Document Archive ───────────────────────────────────────────────

    def _load_document_archive(self):
        """Parse the Document.archive binary plist."""
        for path in ["Document.archive", "document.archive"]:
            try:
                with self._zip.open(path) as f:
                    self._document_archive = plistlib.loads(f.read())
                    self._archive_objects = self._document_archive.get("$objects", [])
                    return
            except (KeyError, Exception):
                continue

    def _resolve_uid(self, uid) -> Any:
        """Resolve a UID reference in the NSKeyedArchiver plist."""
        if uid is None:
            return None
        idx = None
        if isinstance(uid, int):
            idx = uid
        elif hasattr(uid, "data"):  # plistlib.UID
            idx = int.from_bytes(uid.data, "big") if isinstance(uid.data, bytes) else uid.data
        elif isinstance(uid, plistlib.UID):
            idx = uid
            # In Python 3.8+, plistlib.UID can be used as int
            try:
                idx = int(uid)
            except (TypeError, ValueError):
                return None

        if idx is not None and 0 <= idx < len(self._archive_objects):
            return self._archive_objects[idx]
        return None

    def _get_root_object(self) -> Optional[Dict]:
        """Get the root object from the NSKeyedArchiver."""
        if not self._document_archive:
            return None
        top = self._document_archive.get("$top", {})
        root_uid = top.get("root")
        root = self._resolve_uid(root_uid)
        if isinstance(root, dict):
            return root
        # Fallback: try index 1
        if len(self._archive_objects) > 1 and isinstance(self._archive_objects[1], dict):
            return self._archive_objects[1]
        return None

    # ── Metadata Parsing ───────────────────────────────────────────────

    def _parse_metadata(self):
        """Extract metadata from the root document object."""
        root = self._get_root_object()
        if not root:
            return

        # Canvas dimensions – try multiple known key names
        self.canvas_width = self._get_int(root, [
            "SilicaDocumentArchiveDimensionWidth",
            "width", "canvasWidth", "tileSize",
        ])
        self.canvas_height = self._get_int(root, [
            "SilicaDocumentArchiveDimensionHeight",
            "height", "canvasHeight",
        ])

        # If dimensions not found, infer from thumbnail
        if self.canvas_width == 0 and self.thumbnail:
            self.canvas_width = self.thumbnail.width
        if self.canvas_height == 0 and self.thumbnail:
            self.canvas_height = self.thumbnail.height

        # DPI
        dpi = self._get_int(root, ["SilicaDocumentArchiveDPI", "dpi"])
        if dpi > 0:
            self.dpi = dpi

        # Orientation
        self.orientation = self._get_int(root, [
            "SilicaDocumentArchiveOrientation", "orientation",
        ])

        # Video recording
        self.video_enabled = root.get(
            "SilicaDocumentVideoSegmentInfoKey", False
        ) not in (False, None, "$null")

        # Color profile
        cp_uid = root.get("SilicaDocumentArchiveICCProfileData")
        cp = self._resolve_uid(cp_uid)
        if isinstance(cp, str):
            self.color_profile = cp

        # Store human-readable metadata
        for k, v in root.items():
            if isinstance(v, (str, int, float, bool)):
                self.metadata[k] = v

    def _get_int(self, d: dict, keys: list, default: int = 0) -> int:
        """Get an integer value trying multiple key names."""
        for key in keys:
            val = d.get(key)
            if val is None:
                continue
            if isinstance(val, (int, float)):
                return int(val)
            if isinstance(val, (bytes, bytearray)):
                try:
                    return struct.unpack(">i", val[:4])[0]
                except Exception:
                    pass
        return default

    # ── Layer Parsing ──────────────────────────────────────────────────

    def _parse_layers(self):
        """Parse layer information from the archive objects."""
        root = self._get_root_object()
        if not root:
            return

        # Find the layers array UID
        layers_uid = root.get(
            "SilicaDocumentArchiveLayers",
            root.get("layers"),
        )
        layers_ref = self._resolve_uid(layers_uid)

        # If it's an NSArray wrapper, get the objects list
        if isinstance(layers_ref, dict):
            obj_refs = layers_ref.get("NS.objects", [])
        elif isinstance(layers_ref, list):
            obj_refs = layers_ref
        else:
            obj_refs = []

        for ref in obj_refs:
            layer_dict = self._resolve_uid(ref)
            if not isinstance(layer_dict, dict):
                continue

            name = self._resolve_layer_field(layer_dict, ["name", "SilicaLayerArchiveName"])
            if not isinstance(name, str):
                name = f"Layer {len(self.layers) + 1}"

            uuid = self._resolve_layer_field(layer_dict, ["UUID", "uuid", "SilicaLayerArchiveUUID"])
            if not isinstance(uuid, str):
                uuid = ""

            opacity = layer_dict.get(
                "contentsOpacity",
                layer_dict.get("opacity", layer_dict.get("SilicaLayerArchiveOpacity", 1.0)),
            )
            if not isinstance(opacity, (int, float)):
                opacity = 1.0

            visible = not layer_dict.get(
                "hidden",
                layer_dict.get("SilicaLayerArchiveHidden", False),
            )
            if not isinstance(visible, bool):
                visible = True

            blend = layer_dict.get(
                "extendedBlend",
                layer_dict.get("blend", layer_dict.get("blendMode", 0)),
            )
            if not isinstance(blend, (int, float)):
                blend = 0

            layer = ProcreateLayer(
                name=name,
                uuid=uuid,
                opacity=float(opacity),
                visible=visible,
                blend_mode=int(blend),
            )
            self.layers.append(layer)

        # Fallback: scan all objects for layer-like dicts
        if not self.layers:
            self._parse_layers_fallback()

        self.layer_count = len(self.layers) if self.layers else self.layer_count

    def _resolve_layer_field(self, layer_dict: dict, keys: list) -> Any:
        """Resolve a layer field that might be a UID reference."""
        for key in keys:
            val = layer_dict.get(key)
            if val is None:
                continue
            resolved = self._resolve_uid(val)
            if resolved is not None and not isinstance(resolved, dict):
                return resolved
            if isinstance(val, str):
                return val
        return None

    def _parse_layers_fallback(self):
        """Fallback: scan archive objects for anything that looks like a layer."""
        for obj in self._archive_objects:
            if not isinstance(obj, dict):
                continue
            # Check for Silica layer class markers
            cls_ref = obj.get("$class")
            if cls_ref is None:
                continue
            cls_obj = self._resolve_uid(cls_ref)
            if not isinstance(cls_obj, dict):
                continue
            classname = cls_obj.get("$classname", "")
            if "SilicaLayer" not in classname:
                continue

            name_ref = obj.get("name", obj.get("SilicaLayerArchiveName"))
            name = self._resolve_uid(name_ref)
            if not isinstance(name, str):
                name = f"Layer {len(self.layers) + 1}"

            opacity = obj.get("contentsOpacity", obj.get("opacity", 1.0))
            if not isinstance(opacity, (int, float)):
                opacity = 1.0

            visible = not obj.get("hidden", False)

            layer = ProcreateLayer(
                name=name,
                uuid="",
                opacity=float(opacity),
                visible=bool(visible),
                blend_mode=0,
            )
            self.layers.append(layer)

    # ── Layer Image Loading & Compositing ──────────────────────────────

    def _get_tile_size(self) -> int:
        """Get the tile size used for chunk storage."""
        root = self._get_root_object()
        if root:
            ts = self._get_int(root, [
                "tileSize",
                "SilicaDocumentArchiveTileSize",
            ])
            if ts > 0:
                return ts
        return 256

    def load_layer_image(self, layer_index: int) -> Optional[Image.Image]:
        """Load pixel data for a specific layer from chunk files.

        Returns an RGBA Image sized to the canvas, or None if the
        layer's raw data cannot be decoded.
        """
        if not self._zip or layer_index < 0 or layer_index >= len(self.layers):
            return None

        layer = self.layers[layer_index]
        uuid = layer.uuid
        if not uuid:
            return None

        all_names = self._zip.namelist()
        prefix = f"{uuid}/"
        # Accept both .chunk and .lz4 tile files
        _tile_exts = (".chunk", ".lz4")
        chunk_files = [
            n for n in all_names
            if n.startswith(prefix) and n.lower().endswith(_tile_exts)
        ]
        if not chunk_files:
            return None

        tile_size = self._get_tile_size()
        if tile_size <= 0:
            tile_size = 256

        w, h = self.canvas_width, self.canvas_height
        if w <= 0 or h <= 0:
            return None

        cols = max(1, (w + tile_size - 1) // tile_size)
        rows = max(1, (h + tile_size - 1) // tile_size)

        layer_img = Image.new(
            "RGBA", (cols * tile_size, rows * tile_size), (0, 0, 0, 0)
        )
        loaded_any = False
        expected_size = tile_size * tile_size * 4

        for chunk_path in chunk_files:
            basename = chunk_path[len(prefix):]
            # Strip any known tile extension
            name_part = basename
            for _ext in (".chunk", ".lz4"):
                if name_part.lower().endswith(_ext):
                    name_part = name_part[:-len(_ext)]
                    break
            # Support both '_' and '~' as col/row separator
            for sep in ("~", "_"):
                if sep in name_part:
                    parts = name_part.split(sep)
                    break
            else:
                continue
            if len(parts) != 2:
                continue
            try:
                col = int(parts[0])
                row = int(parts[1])
            except ValueError:
                continue

            try:
                raw = self._zip.read(chunk_path)
            except Exception:
                continue

            pixels = None

            # Method 0: bv41 (Apple/Procreate custom lz4 with chained blocks)
            if raw[:4] == b"bv41":
                try:
                    import lz4.block as _lz4b
                    off = 0
                    bv_parts: list = []
                    prev_dict = b""
                    while off < len(raw):
                        if raw[off:off + 4] == b"bv4$":
                            break
                        if raw[off:off + 4] != b"bv41":
                            break
                        off += 4
                        u_size = struct.unpack_from("<I", raw, off)[0]
                        off += 4
                        c_size = struct.unpack_from("<I", raw, off)[0]
                        off += 4
                        chunk = _lz4b.decompress(
                            raw[off:off + c_size],
                            uncompressed_size=u_size,
                            dict=prev_dict,
                        )
                        bv_parts.append(chunk)
                        prev_dict = chunk
                        off += c_size
                    pixels = b"".join(bv_parts)
                except Exception:
                    pixels = None

            # Method 1: uncompressed BGRA
            if pixels is None and len(raw) == expected_size:
                pixels = raw

            # Method 2: lz4 block
            if pixels is None:
                try:
                    import lz4.block
                    pixels = lz4.block.decompress(
                        raw, uncompressed_size=expected_size
                    )
                except Exception:
                    pass

            # Method 3: lzo
            if pixels is None:
                try:
                    import lzo
                    pixels = lzo.decompress(raw, False, expected_size)
                except Exception:
                    pass

            # Method 4: zlib
            if pixels is None:
                try:
                    import zlib
                    pixels = zlib.decompress(raw)
                except Exception:
                    pass

            if pixels is None or len(pixels) != expected_size:
                continue

            tile_img = Image.frombytes(
                "RGBA", (tile_size, tile_size), pixels, "raw", "BGRA"
            )
            layer_img.paste(tile_img, (col * tile_size, row * tile_size))
            loaded_any = True

        if not loaded_any:
            return None

        if layer_img.size != (w, h):
            layer_img = layer_img.crop((0, 0, w, h))
        return layer_img

    def composite_layers(
        self,
        visibility_overrides: Optional[Dict[int, bool]] = None,
    ) -> Optional[Image.Image]:
        """Composite layers respecting custom visibility overrides.

        Args:
            visibility_overrides: ``{layer_index: visible}`` dict that
                overrides every layer's native *visible* flag.

        Returns:
            An RGBA ``Image``, or ``None`` when no layer data could be
            loaded (caller should fall back to ``get_best_image()``).
        """
        if not self.layers:
            return None

        w, h = self.canvas_width, self.canvas_height
        if w <= 0 or h <= 0:
            return None

        result = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        loaded_any = False

        for i, layer in enumerate(self.layers):
            if visibility_overrides and i in visibility_overrides:
                visible = visibility_overrides[i]
            else:
                visible = layer.visible
            if not visible:
                continue

            layer_img = self.load_layer_image(i)
            if layer_img is None:
                continue
            loaded_any = True

            # Apply layer opacity
            if layer.opacity < 1.0:
                r, g, b, a = layer_img.split()
                a = a.point(lambda x, op=layer.opacity: int(x * op))
                layer_img = Image.merge("RGBA", (r, g, b, a))

            result = Image.alpha_composite(result, layer_img)

        return result if loaded_any else None

    # ── Public Helpers ─────────────────────────────────────────────────

    def get_best_image(self) -> Optional[Image.Image]:
        """Return the best available image (composite > thumbnail)."""
        return self.composite or self.thumbnail

    def get_blend_mode_name(self, mode: int) -> str:
        """Get human-readable blend mode name."""
        return self.BLEND_MODES.get(mode, f"Unknown ({mode})")

    def get_file_list(self) -> List[str]:
        """List all entries in the ZIP archive."""
        return self._zip.namelist() if self._zip else []

    def get_file_size(self) -> int:
        """Get the .procreate file size in bytes."""
        return os.path.getsize(self.filepath)

    def get_file_size_human(self) -> str:
        """Get human-readable file size."""
        size = self.get_file_size()
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def export_image(self, output_path: str, fmt: str = "PNG", quality: int = 95):
        """Export the best available image to a standard format."""
        img = self.get_best_image()
        if not img:
            raise ValueError("No image data available to export")
        save_kwargs = {"format": fmt}
        if fmt.upper() in ("JPEG", "JPG"):
            save_kwargs["quality"] = quality
            if img.mode == "RGBA":
                # Flatten alpha for JPEG
                bg = Image.new("RGB", img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[3])
                img = bg
        img.save(output_path, **save_kwargs)

    def extract_thumbnail_bytes(self) -> Optional[bytes]:
        """Get raw PNG bytes of the thumbnail (for shell extension use)."""
        if not self._zip:
            return None
        for path in ["QuickLook/Thumbnail.png", "QuickLook/thumbnail.png", "Thumbnail.png"]:
            try:
                return self._zip.read(path)
            except KeyError:
                continue
        return None

    # ── Context Manager ────────────────────────────────────────────────

    def close(self):
        if self._zip:
            self._zip.close()
            self._zip = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __del__(self):
        self.close()

    def __repr__(self):
        return (
            f"ProcreateFile('{self.filename}', "
            f"{self.canvas_width}x{self.canvas_height}, "
            f"{self.layer_count} layers)"
        )
