# Core performance audit

**Repository:** `ansys/pydynamicreporting`  
**Source revision:** [`2f6d0fc9`](https://github.com/ansys/pydynamicreporting/tree/2f6d0fc9364b76f557a8dcd59568b0e79124210e)  
**Date:** September 17, 2026  

This report records **46 performance opportunities and 5 decisions to retain existing behavior**. The opportunities include **21 local changes or small savings, 23 behavior-sensitive alternatives, and 2 product changes**.

The scope covers all 33 tracked Python modules under `src/ansys/dynamicreporting/core`, relevant code-generation inputs, and the model/rendering/viewer integration in the supplied Ansys Student v261 installation. It includes object loading, saving, serialization, validation, REST requests, array and image conversion, filesystem work, and local and remote HTML export.

The strongest starting points are **H01, H05, H06, H08, and C01**: download buffering, bounded HTML searches, ordinary prefix misses, final document assembly, and repeated JSON parsing. Serverless candidates include **S01, S02, and S04**.

**Current** contains the code at the cited revision. **Proposed** replaces that span unless an insertion is specified. **Alternative** identifies an approach with unresolved behavior differences; keep the current implementation under the strict compatibility requirement. Overlapping changes must be combined, not applied as independent replacements.

The installation excerpts come from `E:\Program Files\ANSYS Inc\ANSYS Student\v261\CEI\nexus261`. Other installation versions can differ. Every candidate must preserve existing APIs, output, errors, ordering, and supported customizations without adding third-party packages.

## Change types

| Type | Entries | Meaning |
| --- | ---: | --- |
| Local change | 14 | Removes repeated work inside one operation, subject to the stated input guards. |
| Behavior-sensitive | 23 | Changes observable behavior; retain the current code until the stated differences are resolved. |
| Small saving | 7 | Avoids a small allocation or repeated lookup; benefit depends on workload. |
| Product change | 2 | Requires a supported change in the Ansys product, outside the client. |
| Keep current behavior | 5 | The apparent shortcut changes an existing contract. |

## Contents

| Group | Entries |
| --- | --- |
| HTML export | [H01](#h01), [H02](#h02), [H03](#h03), [H04](#h04), [H05](#h05), [H06](#h06), [H07](#h07), [H08](#h08) |
| REST parameters and numerical data | [C01: all 62 methods](#c01), [C02](#c02), [C03](#c03), [C04](#c04), [C05](#c05) |
| Serverless and validation | [S01](#s01), [S02](#s02), [S03](#s03), [S04](#s04), [S05](#s05) |
| Supporting utilities | [U01](#u01), [U02](#u02), [U03](#u03), [U04](#u04), [U05](#u05), [U06](#u06), [U07](#u07) |
| Conditional, smaller, product-owned and retained work | [D01–D09](#d01), [M01–M10](#m01), [P01–P02](#p01), [R01–R05](#r01) |


<a id="h01"></a>

## H01. Accumulate downloaded bytes without repeated concatenation

**Local change.** Three asset-download paths repeatedly copy the complete accumulated response. A bytearray keeps chunk handling in the same order and produces immutable bytes once.

**Compatibility:** The final content object remains bytes. Preserve empty-chunk handling, response decoding, status handling, and existing write/error boundaries. Release the temporary bytearray after conversion so it is not retained during asset rewrites and writes. This still buffers the complete response; it does not impose a memory limit.

Reference: [Python sequence construction](https://docs.python.org/3.10/library/stdtypes.html#common-sequence-operations).

<details>
<summary>utils/report_download_html.py:365–368</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_download_html.py#L365-L368)  
**Lines:** 365–368

Replace only the accumulation block. Leave the existing request, surrounding try/except, transformations, and writes in place.

**Current**

```python
                    content = b""
                    for chunk in resp.iter_content(chunk_size=65536):
                        if chunk:
                            content += chunk
```

**Proposed**

```python
                    content_buffer = bytearray()
                    for chunk in resp.iter_content(chunk_size=65536):
                        if chunk:
                            content_buffer.extend(chunk)
                    content = bytes(content_buffer)
                    del content_buffer
```

</details>

<details>
<summary>utils/report_download_html.py:401–404</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_download_html.py#L401-L404)  
**Lines:** 401–404

Replace only the accumulation block. Leave the existing request, surrounding try/except, transformations, and writes in place.

**Current**

```python
                    content = b""
                    for chunk in resp.iter_content(chunk_size=65536):
                        if chunk:
                            content += chunk
```

**Proposed**

```python
                    content_buffer = bytearray()
                    for chunk in resp.iter_content(chunk_size=65536):
                        if chunk:
                            content_buffer.extend(chunk)
                    content = bytes(content_buffer)
                    del content_buffer
```

</details>

<details>
<summary>utils/report_download_html.py:448–451</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_download_html.py#L448-L451)  
**Lines:** 448–451

Replace only the accumulation block. Leave the existing request, surrounding try/except, transformations, and writes in place.

**Current**

```python
                content = b""
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        content += chunk
```

**Proposed**

```python
                content_buffer = bytearray()
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        content_buffer.extend(chunk)
                content = bytes(content_buffer)
                del content_buffer
```

</details>

[Back to contents](#contents)

<a id="h02"></a>

## H02. Assemble each HTML replacement pass once

**Behavior-sensitive.** Both `_replace_blocks` implementations copy the complete document after each replacement. Joining unchanged spans and processed blocks removes that repeated copying.

**Compatibility:** With the built-in finders, scanning the original suffix preserves block selection. An overridden finder instead receives the original document and original offsets, whereas the current loop passes the rewritten document and adjusted offsets. A non-string replacement also fails later at `join`, after subsequent asset processing. Preserve the existing path for those customizations before adopting this approach. Keep separate passes, asset order, and the remote-only reset of `_replaced_file_ext`.

<details>
<summary>serverless/html_exporter.py:593–605</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/serverless/html_exporter.py#L593-L605)  
**Lines:** 593–605

**Current**

```python
    def _replace_blocks(
        self, html: str, prefix: str, suffix: str, inline: bool = False, size_check: bool = False
    ) -> str:
        """Iteratively finds and replaces all asset references within matching blocks."""
        current_pos = 0
        while True:
            start, end, text_block = self._find_block(html, current_pos, prefix, suffix)
            if start < 0:
                break
            processed_text = self._replace_files(text_block, inline=inline, size_check=size_check)
            html = html[:start] + processed_text + html[end:]
            current_pos = start + len(processed_text)
        return html
```

**Alternative**

```python
    def _replace_blocks(
        self, html: str, prefix: str, suffix: str, inline: bool = False, size_check: bool = False
    ) -> str:
        """Iteratively finds and replaces all asset references within matching blocks."""
        current_pos = 0
        parts = []
        while True:
            start, end, text_block = self._find_block(html, current_pos, prefix, suffix)
            if start < 0:
                break
            processed_text = self._replace_files(text_block, inline=inline, size_check=size_check)
            parts.extend((html[current_pos:start], processed_text))
            current_pos = end
        parts.append(html[current_pos:])
        return "".join(parts)
```

</details>

<details>
<summary>utils/report_download_html.py:536–550</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_download_html.py#L536-L550)  
**Lines:** 536–550

**Current**

```python
    def _replace_blocks(
        self, html: str, prefix: str, suffix: str, inline: bool = False, size_check: bool = False
    ) -> str:
        # track the filename extension for the last replacement
        self._replaced_file_ext = None
        # walk all the matching blocks
        current_pos = 0
        while True:
            start, end, text = self.find_block(html, current_pos, prefix, suffix)
            if start < 0:
                break
            text = self._replace_files(text, inline=inline, size_check=size_check)
            html = html[:start] + text + html[end:]
            current_pos = start + len(text)
        return html
```

**Alternative**

```python
    def _replace_blocks(
        self, html: str, prefix: str, suffix: str, inline: bool = False, size_check: bool = False
    ) -> str:
        # track the filename extension for the last replacement
        self._replaced_file_ext = None
        # walk all the matching blocks
        current_pos = 0
        parts = []
        while True:
            start, end, text = self.find_block(html, current_pos, prefix, suffix)
            if start < 0:
                break
            text = self._replace_files(text, inline=inline, size_check=size_check)
            parts.extend((html[current_pos:start], text))
            current_pos = end
        parts.append(html[current_pos:])
        return "".join(parts)
```

</details>

[Back to contents](#contents)

<a id="h03"></a>

## H03. Assemble viewer-component replacements once

**Behavior-sensitive.** Inlining each `ansys-nexus-viewer` currently copies the complete HTML document again. Joining the completed viewer blocks removes those full-document copies.

**Compatibility:** As in H02, custom finders observe different document contents and offsets, and invalid replacement types can fail later. Preserve the existing path for overrides. Keep proxy-before-source processing, `src_ext` insertion, cumulative inline-size state, and the different local/remote size-exception rewrites.

<details>
<summary>serverless/html_exporter.py:651–671</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/serverless/html_exporter.py#L651-L671)  
**Lines:** 651–671

**Current**

```python
    def _inline_ansys_viewer(self, html: str) -> str:
        """Handles the special case of inlining assets for the <ansys-nexus-viewer> component."""
        current_pos = 0
        while True:
            start, end, text_block = self._find_block(
                html, current_pos, "<ansys-nexus-viewer", "</ansys-nexus-viewer>"
            )
            if start < 0:
                break
            # Legacy parity: always inline viewer attributes
            text = self._replace_blocks(text_block, 'proxy_img="', '"', inline=True)
            text = self._replace_blocks(text, 'src="', '"', inline=True, size_check=True)
            if "__SIZE_EXCEPTION__" in text:
                msg = "3D geometry too large for stand-alone HTML file"
                text = text.replace('src="__SIZE_EXCEPTION__"', f'src="" proxy_only="{msg}"')
            if self._replaced_file_ext:
                ext = self._replaced_file_ext.replace(".", "").upper()
                text = text.replace("<ansys-nexus-viewer", f'<ansys-nexus-viewer src_ext="{ext}"')
            html = html[:start] + text + html[end:]
            current_pos = start + len(text)
        return html
```

**Alternative**

```python
    def _inline_ansys_viewer(self, html: str) -> str:
        """Handles the special case of inlining assets for the <ansys-nexus-viewer> component."""
        current_pos = 0
        parts = []
        while True:
            start, end, text_block = self._find_block(
                html, current_pos, "<ansys-nexus-viewer", "</ansys-nexus-viewer>"
            )
            if start < 0:
                break
            # Legacy parity: always inline viewer attributes
            text = self._replace_blocks(text_block, 'proxy_img="', '"', inline=True)
            text = self._replace_blocks(text, 'src="', '"', inline=True, size_check=True)
            if "__SIZE_EXCEPTION__" in text:
                msg = "3D geometry too large for stand-alone HTML file"
                text = text.replace('src="__SIZE_EXCEPTION__"', f'src="" proxy_only="{msg}"')
            if self._replaced_file_ext:
                ext = self._replaced_file_ext.replace(".", "").upper()
                text = text.replace("<ansys-nexus-viewer", f'<ansys-nexus-viewer src_ext="{ext}"')
            parts.extend((html[current_pos:start], text))
            current_pos = end
        parts.append(html[current_pos:])
        return "".join(parts)
```

</details>

<details>
<summary>utils/report_download_html.py:552–578</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_download_html.py#L552-L578)  
**Lines:** 552–578

**Current**

```python
    def _inline_ansys_viewer(self, html: str) -> str:
        #  AVZ component interface
        # <ansys-nexus-viewer proxy_img="/media/ca0845e2-1edd-11ec-8c57-381428170733_scene/proxy.png" active=false
        # ... aspect_ratio="proxy" src="/media/ca0845e2-1edd-11ec-8c57-381428170733_scene/scene.avz"
        # ... id="avz_comp_042395948b40418b81a48f2ffbb7fa2a"></ansys-nexus-viewer>
        current_pos = 0
        while True:
            start, end, text = self.find_block(
                html, current_pos, "<ansys-nexus-viewer", "</ansys-nexus-viewer>"
            )
            if start < 0:
                break
            text = self._replace_blocks(text, 'proxy_img="', '"', inline=True)
            text = self._replace_blocks(text, 'src="', '"', inline=True, size_check=True)
            # handle any size check exception
            if "__SIZE_EXCEPTION__" in text:
                # convert src="__SIZE_EXCEPTION__" to: src="" proxy_only="Hover text"
                msg = "3D geometry too large for stand-alone HTML file"
                text = text.replace("__SIZE_EXCEPTION__", f'" proxy_only="{msg}')
            # if the src was replaced with a data URI, we need to inject the src_ext attribute so
            # that the component knows what the source file format is.
            if self._replaced_file_ext:
                ext = self._replaced_file_ext.replace(".", "").upper()
                text = text.replace("<ansys-nexus-viewer", f'<ansys-nexus-viewer src_ext="{ext}"')
            html = html[:start] + text + html[end:]
            current_pos = start + len(text)
        return html
```

**Alternative**

```python
    def _inline_ansys_viewer(self, html: str) -> str:
        #  AVZ component interface
        # <ansys-nexus-viewer proxy_img="/media/ca0845e2-1edd-11ec-8c57-381428170733_scene/proxy.png" active=false
        # ... aspect_ratio="proxy" src="/media/ca0845e2-1edd-11ec-8c57-381428170733_scene/scene.avz"
        # ... id="avz_comp_042395948b40418b81a48f2ffbb7fa2a"></ansys-nexus-viewer>
        current_pos = 0
        parts = []
        while True:
            start, end, text = self.find_block(
                html, current_pos, "<ansys-nexus-viewer", "</ansys-nexus-viewer>"
            )
            if start < 0:
                break
            text = self._replace_blocks(text, 'proxy_img="', '"', inline=True)
            text = self._replace_blocks(text, 'src="', '"', inline=True, size_check=True)
            # handle any size check exception
            if "__SIZE_EXCEPTION__" in text:
                # convert src="__SIZE_EXCEPTION__" to: src="" proxy_only="Hover text"
                msg = "3D geometry too large for stand-alone HTML file"
                text = text.replace("__SIZE_EXCEPTION__", f'" proxy_only="{msg}')
            # if the src was replaced with a data URI, we need to inject the src_ext attribute so
            # that the component knows what the source file format is.
            if self._replaced_file_ext:
                ext = self._replaced_file_ext.replace(".", "").upper()
                text = text.replace("<ansys-nexus-viewer", f'<ansys-nexus-viewer src_ext="{ext}"')
            parts.extend((html[current_pos:start], text))
            current_pos = end
        parts.append(html[current_pos:])
        return "".join(parts)
```

</details>

[Back to contents](#contents)

<a id="h04"></a>

## H04. Avoid repeated string rebuilding inside asset-reference blocks

**Behavior-sensitive.** The URL-replacement loop repeatedly copies long blocks, including key_images lists and scene binary-load lists.

**Compatibility:** The proposal retains the existing prefix-priority search rather than choosing the earliest path across all prefixes. For boundary cases, the old loop searches a mutated string, and quote inference can observe previously inserted text for malformed or unusual adjacent references. These cases can produce different output. Keep the current loop for strict compatibility; H06 provides a narrower improvement without changing the string being searched.

<details>
<summary>serverless/html_exporter.py:188–251</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/serverless/html_exporter.py#L188-L251)  
**Lines:** 188–251

Unusual custom prefixes and malformed references can change replacement behavior.

**Current**

```python
    def _replace_files(self, text: str, inline: bool = False, size_check: bool = False) -> str:
        """
        Finds, processes, and replaces all asset references within a given block of text.

        IMPORTANT: This mirrors the legacy behavior exactly:
          - Only these prefixes are recognized, in this strict priority order:
              /static/ansys{ver}/, /static/, /media/, /ansys{ver}/
          - It picks the FIRST pattern in that list that occurs anywhere at/after `current`
            (it does NOT choose the earliest occurrence across all patterns).
          - No './' variants, no generic normalization.
        """
        self._replaced_file_ext = None
        current = 0
        ver = str(self._ansys_version) if self._ansys_version is not None else ""

        patterns = []
        if ver:
            patterns.append(f"{self._static_url}ansys{ver}/")
        patterns.extend([self._static_url, self._media_url])
        if ver:
            patterns.append(f"/ansys{ver}/")

        while True:
            # Find the next match using the legacy priority order
            idx1 = -1
            matched_pattern = ""
            for pat in patterns:
                pos = text.find(pat, current)
                if pos != -1:
                    idx1 = pos
                    matched_pattern = pat
                    break
            if idx1 == -1:
                return text  # nothing more to replace

            # The generic ``<script ...>`` pass runs after the dedicated
            # ``<script src=...>`` pass, so already-rewritten relative paths can
            # appear here as ``./media/...`` or ``./ansys...``.  Those are
            # already export-safe and should not be re-processed with the legacy
            # quote heuristic, which would otherwise truncate them at the next
            # ``.`` (for example ``./media/jquery.min.js`` -> ``/media/jquery``).
            if idx1 > 0 and text[idx1 - 1] == ".":
                current = idx1 + len(matched_pattern)
                continue

            # Legacy heuristic: assume we're inside an attribute quoted by the char before the path
            quote = text[idx1 - 1]
            idx2 = text.find(quote, idx1)
            if idx2 == -1:
                return text  # no closing quote -> stop processing this block safely

            path_in_html = text[idx1:idx2]  # includes any query string
            # Strip query/cache-buster for filesystem lookups (legacy parity)
            simple_path = path_in_html.split("?", 1)[0]

            _, ext = os.path.splitext(simple_path)
            self._replaced_file_ext = ext

            new_path = self._process_file(path_in_html, simple_path, inline=inline)
            if size_check and self._inline_size_exception:
                new_path = "__SIZE_EXCEPTION__"

            text = text[:idx1] + new_path + text[idx2:]
            current = idx1 + len(new_path)
```

**Alternative**

```python
    def _replace_files(self, text: str, inline: bool = False, size_check: bool = False) -> str:
        """
        Finds, processes, and replaces all asset references within a given block of text.

        Keep the existing prefix priority:
          - Only these prefixes are recognized, in this strict priority order:
              /static/ansys{ver}/, /static/, /media/, /ansys{ver}/
          - It picks the FIRST pattern in that list that occurs anywhere at/after `current`
            (it does NOT choose the earliest occurrence across all patterns).
          - No './' variants, no generic normalization.
        """
        self._replaced_file_ext = None
        current = 0
        copied_until = 0
        parts = []
        ver = str(self._ansys_version) if self._ansys_version is not None else ""

        patterns = []
        if ver:
            patterns.append(f"{self._static_url}ansys{ver}/")
        patterns.extend([self._static_url, self._media_url])
        if ver:
            patterns.append(f"/ansys{ver}/")

        while True:
            # Find the next match using the legacy priority order
            idx1 = -1
            matched_pattern = ""
            for pat in patterns:
                pos = text.find(pat, current)
                if pos != -1:
                    idx1 = pos
                    matched_pattern = pat
                    break
            if idx1 == -1:
                return "".join(parts + [text[copied_until:]])  # nothing more to replace

            # The generic ``<script ...>`` pass runs after the dedicated
            # ``<script src=...>`` pass, so already-rewritten relative paths can
            # appear here as ``./media/...`` or ``./ansys...``.  Those are
            # already export-safe and should not be re-processed with the legacy
            # quote heuristic, which would otherwise truncate them at the next
            # ``.`` (for example ``./media/jquery.min.js`` -> ``/media/jquery``).
            if idx1 > 0 and text[idx1 - 1] == ".":
                current = idx1 + len(matched_pattern)
                continue

            # Legacy heuristic: assume we're inside an attribute quoted by the char before the path
            quote = text[idx1 - 1]
            idx2 = text.find(quote, idx1)
            if idx2 == -1:
                return "".join(parts + [text[copied_until:]])  # no closing quote -> stop processing this block safely

            path_in_html = text[idx1:idx2]  # includes any query string
            # Strip query/cache-buster for filesystem lookups (legacy parity)
            simple_path = path_in_html.split("?", 1)[0]

            _, ext = os.path.splitext(simple_path)
            self._replaced_file_ext = ext

            new_path = self._process_file(path_in_html, simple_path, inline=inline)
            if size_check and self._inline_size_exception:
                new_path = "__SIZE_EXCEPTION__"

            parts.extend((text[copied_until:idx1], new_path))
            copied_until = idx2
            current = idx2
```

</details>

<details>
<summary>utils/report_download_html.py:120–163</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_download_html.py#L120-L163)  
**Lines:** 120–163

Unusual custom prefixes and malformed references can change replacement behavior.

**Current**

```python
    def _replace_files(self, text: str, inline: bool = False, size_check: bool = False) -> str:
        # track the filename extension for the last replacement
        self._replaced_file_ext = None
        # we might have multiple replacements
        current = 0
        while True:
            try:
                idx1 = text.index(f"/static/ansys{self._ansys_version}/", current)
            except ValueError:
                try:
                    idx1 = text.index("/static/", current)
                except ValueError:
                    try:
                        idx1 = text.index("/media/", current)
                    except ValueError:
                        try:
                            idx1 = text.index(f"/ansys{self._ansys_version}/", current)
                        except ValueError:
                            return text
            quote = text[idx1 - 1]
            try:
                idx2 = text.index(quote, idx1)
            except ValueError:
                return text
            path = text[idx1:idx2]
            # We may have a path that includes queries (e.g. /media/filename.png?query...)
            # We need the query for the purposes of the GET operation to download the item,
            # but once saved to disk, we need to drop the query portion of the path.
            # 'simple_path' is the stripped down filename (used in the cache).
            simple_path = path
            if "?" in path:
                tmp = path.index("?")
                simple_path = path[:tmp]
            # Capture the last replaced filename extension.  Needed for the inline situation.
            (_, ext) = os.path.splitext(simple_path)
            self._replaced_file_ext = ext
            # get the actual new file
            new_path = self._get_file(path, simple_path, inline=inline)
            # if we had size checking enabled replacement resulted in a sizing exception,
            # we need to substitute a tag that can be replaced later.
            if size_check and self._inline_size_exception:
                new_path = "__SIZE_EXCEPTION__"
            text = text[:idx1] + new_path + text[idx2:]
            current = idx1 + len(new_path)
```

**Alternative**

```python
    def _replace_files(self, text: str, inline: bool = False, size_check: bool = False) -> str:
        # track the filename extension for the last replacement
        self._replaced_file_ext = None
        # we might have multiple replacements
        current = 0
        copied_until = 0
        parts = []
        while True:
            try:
                idx1 = text.index(f"/static/ansys{self._ansys_version}/", current)
            except ValueError:
                try:
                    idx1 = text.index("/static/", current)
                except ValueError:
                    try:
                        idx1 = text.index("/media/", current)
                    except ValueError:
                        try:
                            idx1 = text.index(f"/ansys{self._ansys_version}/", current)
                        except ValueError:
                            return "".join(parts + [text[copied_until:]])
            quote = text[idx1 - 1]
            try:
                idx2 = text.index(quote, idx1)
            except ValueError:
                return "".join(parts + [text[copied_until:]])
            path = text[idx1:idx2]
            # We may have a path that includes queries (e.g. /media/filename.png?query...)
            # We need the query for the purposes of the GET operation to download the item,
            # but once saved to disk, we need to drop the query portion of the path.
            # 'simple_path' is the stripped down filename (used in the cache).
            simple_path = path
            if "?" in path:
                tmp = path.index("?")
                simple_path = path[:tmp]
            # Capture the last replaced filename extension.  Needed for the inline situation.
            (_, ext) = os.path.splitext(simple_path)
            self._replaced_file_ext = ext
            # get the actual new file
            new_path = self._get_file(path, simple_path, inline=inline)
            # if we had size checking enabled replacement resulted in a sizing exception,
            # we need to substitute a tag that can be replaced later.
            if size_check and self._inline_size_exception:
                new_path = "__SIZE_EXCEPTION__"
            parts.extend((text[copied_until:idx1], new_path))
            copied_until = idx2
            current = idx2
```

</details>

[Back to contents](#contents)

<a id="h05"></a>

## H05. Search within block bounds before slicing

**Local change.** Rejected blocks are copied solely to check whether they contain asset paths. The remote method also takes a second identical slice on success.

**Compatibility:** Use bounded string searches and a bounded regex match anchored at the block start. Preserve the configured local prefixes and remote matching behavior. The smallest remote-only change is to return its existing block variable at line 533.

<details>
<summary>serverless/html_exporter.py:561–591</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/serverless/html_exporter.py#L561-L591)  
**Lines:** 561–591

**Current**

```python
    def _find_block(self, text: str, start: int, prefix: str, suffix: str) -> tuple[int, int, str]:
        """
        Legacy-compatible: return the next [prefix ... suffix] block that contains at least
        one asset-like reference. Accept the configured custom prefixes and the dynamic
        /ansys<ver>/ root. No hard-coded legacy literals.
        """
        custom_static = (self._static_url or "").strip()
        custom_media = (self._media_url or "").strip()
        ver = str(self._ansys_version) if self._ansys_version is not None else ""

        while True:
            try:
                idx1 = text.index(prefix, start)
            except ValueError:
                return -1, -1, ""
            try:
                idx2 = text.index(suffix, idx1 + len(prefix))
            except ValueError:
                return -1, -1, ""
            idx2 += len(suffix)

            block = text[idx1:idx2]

            if (
                (custom_static and custom_static in block)
                or (custom_media and custom_media in block)
                or (ver and f"/ansys{ver}/" in block)
            ):
                return idx1, idx2, block

            start = idx2
```

**Proposed**

```python
    def _find_block(self, text: str, start: int, prefix: str, suffix: str) -> tuple[int, int, str]:
        """
        Legacy-compatible: return the next [prefix ... suffix] block that contains at least
        one asset-like reference. Accept the configured custom prefixes and the dynamic
        /ansys<ver>/ root. No hard-coded legacy literals.
        """
        custom_static = (self._static_url or "").strip()
        custom_media = (self._media_url or "").strip()
        ver = str(self._ansys_version) if self._ansys_version is not None else ""

        while True:
            try:
                idx1 = text.index(prefix, start)
            except ValueError:
                return -1, -1, ""
            try:
                idx2 = text.index(suffix, idx1 + len(prefix))
            except ValueError:
                return -1, -1, ""
            idx2 += len(suffix)

            if (
                (custom_static and text.find(custom_static, idx1, idx2) != -1)
                or (custom_media and text.find(custom_media, idx1, idx2) != -1)
                or (ver and text.find(f"/ansys{ver}/", idx1, idx2) != -1)
            ):
                return idx1, idx2, text[idx1:idx2]

            start = idx2
```

</details>

<details>
<summary>utils/report_download_html.py:499–534</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_download_html.py#L499-L534)  
**Lines:** 499–534

**Current**

```python
    def find_block(text: str, start: int, prefix: str, suffix: str) -> tuple[int, int, str]:
        """
        Finds a block of text between a prefix and a suffix that contains a valid asset path.

        This method searches for a substring that starts with 'prefix', ends with 'suffix',
        and contains a reference to '/media/', '/static/', or a versioned ansys path
        like '/ansys242/'.

        Args:
            text: The string to search within.
            start: The starting index for the search.
            prefix: The string that marks the beginning of the block.
            suffix: The string that marks the end of the block.

        Returns:
            A tuple containing the start index, end index, and the found block text.
            If no block is found, it returns (-1, -1, "").
        """
        while True:
            try:
                idx1 = text.index(prefix, start)
            except ValueError:
                return -1, -1, ""
            try:
                idx2 = text.index(suffix, idx1 + len(prefix))
            except ValueError:
                return -1, -1, ""
            idx2 += len(suffix)
            block = text[idx1:idx2]
            if (
                ("/media/" in block)
                or ("/static/" in block)
                or (re.match(r"/ansys([0-9]+)", block))
            ):
                return idx1, idx2, text[idx1:idx2]
            start = idx2
```

**Proposed**

```python
    def find_block(text: str, start: int, prefix: str, suffix: str) -> tuple[int, int, str]:
        """
        Finds a block of text between a prefix and a suffix that contains a valid asset path.

        This method searches for a substring that starts with 'prefix', ends with 'suffix',
        and contains a reference to '/media/', '/static/', or a versioned ansys path
        like '/ansys242/'.

        Args:
            text: The string to search within.
            start: The starting index for the search.
            prefix: The string that marks the beginning of the block.
            suffix: The string that marks the end of the block.

        Returns:
            A tuple containing the start index, end index, and the found block text.
            If no block is found, it returns (-1, -1, "").
        """
        version_path = re.compile(r"/ansys([0-9]+)")
        while True:
            try:
                idx1 = text.index(prefix, start)
            except ValueError:
                return -1, -1, ""
            try:
                idx2 = text.index(suffix, idx1 + len(prefix))
            except ValueError:
                return -1, -1, ""
            idx2 += len(suffix)
            if (
                (text.find("/media/", idx1, idx2) != -1)
                or (text.find("/static/", idx1, idx2) != -1)
                or (version_path.match(text, idx1, idx2))
            ):
                return idx1, idx2, text[idx1:idx2]
            start = idx2
```

</details>

[Back to contents](#contents)

<a id="h06"></a>

## H06. Avoid exceptions for ordinary asset-prefix misses

**Local change.** `_replace_files` uses nested `index` calls to choose an asset prefix. Missing prefixes raise and catch up to four `ValueError` exceptions per search. `find` reports the same misses without those exceptions.

**Compatibility:** Keep the existing prefix priority, current search offset, and rewritten text. Do not select the earliest occurrence across all prefixes. Quote inference, query handling, cache keys, and asset processing stay in the existing loop. String subclasses retain their original `index` calls.

Reference: [Python str.find and str.index](https://docs.python.org/3.10/library/stdtypes.html#str.find).

<details>
<summary>utils/report_download_html.py:126–138</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_download_html.py#L126-L138)  
**Lines:** 126–138

**Current**

```python
            try:
                idx1 = text.index(f"/static/ansys{self._ansys_version}/", current)
            except ValueError:
                try:
                    idx1 = text.index("/static/", current)
                except ValueError:
                    try:
                        idx1 = text.index("/media/", current)
                    except ValueError:
                        try:
                            idx1 = text.index(f"/ansys{self._ansys_version}/", current)
                        except ValueError:
                            return text
```

**Proposed**

```python
            if type(text) is str:
                idx1 = text.find(f"/static/ansys{self._ansys_version}/", current)
                if idx1 < 0:
                    idx1 = text.find("/static/", current)
                if idx1 < 0:
                    idx1 = text.find("/media/", current)
                if idx1 < 0:
                    idx1 = text.find(f"/ansys{self._ansys_version}/", current)
                if idx1 < 0:
                    return text
            else:
                try:
                    idx1 = text.index(f"/static/ansys{self._ansys_version}/", current)
                except ValueError:
                    try:
                        idx1 = text.index("/static/", current)
                    except ValueError:
                        try:
                            idx1 = text.index("/media/", current)
                        except ValueError:
                            try:
                                idx1 = text.index(f"/ansys{self._ansys_version}/", current)
                            except ValueError:
                                return text
```

</details>

[Back to contents](#contents)

<a id="h07"></a>

## H07. Normalize scene filenames once

**Small saving.** The remote scene check uppercases a filename up to four times. One uppercase conversion and a tuple of suffixes avoid those repeated string allocations.

**Compatibility:** Keep all four extensions and case-insensitive matching. The existing path remains for custom string-like objects, whose `upper` or `endswith` methods may be observable. Retain the existing `staticmethod` decorator.

<details>
<summary>utils/report_download_html.py:424–433</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_download_html.py#L424-L433)  
**Lines:** 424–433

**Current**

```python
    def is_scene_file(name: str) -> bool:
        if name.upper().endswith(".AVZ"):
            return True
        if name.upper().endswith(".SCDOC"):
            return True
        if name.upper().endswith(".SCDOCX"):
            return True
        if name.upper().endswith(".GLB"):
            return True
        return False
```

**Proposed**

```python
    def is_scene_file(name: str) -> bool:
        if type(name) is str:
            return name.upper().endswith((".AVZ", ".SCDOC", ".SCDOCX", ".GLB"))
        if name.upper().endswith(".AVZ"):
            return True
        if name.upper().endswith(".SCDOC"):
            return True
        if name.upper().endswith(".SCDOCX"):
            return True
        if name.upper().endswith(".GLB"):
            return True
        return False
```

</details>

[Back to contents](#contents)

<a id="h08"></a>

## H08. Assemble the final local HTML document once

**Local change.** The final `head + body_open + text + body_close` expression copies the fragment into an intermediate string and then copies it again. Joining the four pieces creates one result.

**Compatibility:** Keep the exact header, body markup, whitespace handling, and complete-document shortcut. The fast path applies only to plain strings; custom string results from `lstrip` keep the original addition behavior. This change can be used independently of H02–H04 and M01.

Reference: [Python str.join](https://docs.python.org/3.10/library/stdtypes.html#str.join).

<details>
<summary>serverless/html_exporter.py:186</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/serverless/html_exporter.py#L186)  
**Lines:** 186

**Current**

```python
        return head + body_open + text + body_close
```

**Proposed**

```python
        if type(text) is str:
            return "".join((head, body_open, text, body_close))
        return head + body_open + text + body_close
```

</details>

[Back to contents](#contents)

<a id="c01"></a>

## C01. Parse each REST parameter document once per method call

**Local change.** Repeated json.loads(self.params) appears in 62 methods, including 61 getters and one mutator. Large parameter documents are parsed repeatedly inside a single accessor.

**Compatibility:** Keep existing defaults, nested JSON decoding, error branches, and mutable return values. The proposals intentionally retain get_transpose's HTML lookup and get_postgre's missing-username expression. Do not cache parsed parameters across calls.

The 62 methods below comprise 61 getters and `tablemergeREST.add_ids`. Repeated names belong to different classes; each block includes its owning class. The only mutator uses a separate shallow dictionary copy so its local key insertion does not change the later original-JSON lookup.

<details>
<summary>TemplateREST.get_sort_fields — utils/report_objects.py:1585–1590</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L1585-L1590)  
**Lines:** 1585–1590

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_sort_fields(self):
        if "sort_fields" in json.loads(self.params):
            return json.loads(self.params)["sort_fields"]
        else:
            return []
```

**Proposed**

```python
    def get_sort_fields(self):
        parsed_params = json.loads(self.params)
        if "sort_fields" in parsed_params:
            return parsed_params["sort_fields"]
        else:
            return []
```

</details>

<details>
<summary>TemplateREST.get_property — utils/report_objects.py:1591–1596</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L1591-L1596)  
**Lines:** 1591–1596

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_property(self):
        if "properties" in json.loads(self.params):
            return json.loads(self.params)["properties"]
        else:
            return {}
```

**Proposed**

```python
    def get_property(self):
        parsed_params = json.loads(self.params)
        if "properties" in parsed_params:
            return parsed_params["properties"]
        else:
            return {}
```

</details>

<details>
<summary>TemplateREST.get_sort_selection — utils/report_objects.py:1636–1641</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L1636-L1641)  
**Lines:** 1636–1641

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_sort_selection(self):
        if "sort_selection" in json.loads(self.params):
            return json.loads(self.params)["sort_selection"]
        else:
            return ""
```

**Proposed**

```python
    def get_sort_selection(self):
        parsed_params = json.loads(self.params)
        if "sort_selection" in parsed_params:
            return parsed_params["sort_selection"]
        else:
            return ""
```

</details>

<details>
<summary>TemplateREST.get_filter_mode — utils/report_objects.py:1667–1672</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L1667-L1672)  
**Lines:** 1667–1672

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_filter_mode(self):
        if "filter_type" in json.loads(self.params):
            return json.loads(self.params)["filter_type"]
        else:
            return "items"
```

**Proposed**

```python
    def get_filter_mode(self):
        parsed_params = json.loads(self.params)
        if "filter_type" in parsed_params:
            return parsed_params["filter_type"]
        else:
            return "items"
```

</details>

<details>
<summary>TemplateREST.get_html — utils/report_objects.py:1683–1691</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L1683-L1691)  
**Lines:** 1683–1691

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_html(self):
        if "Layout:" in self.report_type:
            if "HTML" in json.loads(self.params):
                return json.loads(self.params)["HTML"]
            else:
                return ""
        else:
            raise ValueError(f"Error: HTML not supported on the report type {self.report_type}")
```

**Proposed**

```python
    def get_html(self):
        if "Layout:" in self.report_type:
            parsed_params = json.loads(self.params)
            if "HTML" in parsed_params:
                return parsed_params["HTML"]
            else:
                return ""
        else:
            raise ValueError(f"Error: HTML not supported on the report type {self.report_type}")
```

</details>

<details>
<summary>LayoutREST.get_column_count — utils/report_objects.py:1738–1743</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L1738-L1743)  
**Lines:** 1738–1743

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_column_count(self):
        if "column_count" in json.loads(self.params):
            return json.loads(self.params)["column_count"]
        else:
            return 1
```

**Proposed**

```python
    def get_column_count(self):
        parsed_params = json.loads(self.params)
        if "column_count" in parsed_params:
            return parsed_params["column_count"]
        else:
            return 1
```

</details>

<details>
<summary>LayoutREST.get_column_widths — utils/report_objects.py:1754–1759</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L1754-L1759)  
**Lines:** 1754–1759

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_column_widths(self):
        if "column_widths" in json.loads(self.params):
            return json.loads(self.params)["column_widths"]
        else:
            return [1.0]
```

**Proposed**

```python
    def get_column_widths(self):
        parsed_params = json.loads(self.params)
        if "column_widths" in parsed_params:
            return parsed_params["column_widths"]
        else:
            return [1.0]
```

</details>

<details>
<summary>LayoutREST.get_transpose — utils/report_objects.py:1792–1802</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L1792-L1802)  
**Lines:** 1792–1802

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_transpose(self):
        if "Layout:" in self.report_type:
            if "transpose" in json.loads(self.params):
                return json.loads(self.params)["HTML"]
            else:
                return 0
        else:
            raise ValueError(
                f"Error: transpose columns/rows not supported on the report type {self.report_type}"
            )
```

**Proposed**

```python
    def get_transpose(self):
        if "Layout:" in self.report_type:
            parsed_params = json.loads(self.params)
            if "transpose" in parsed_params:
                return parsed_params["HTML"]
            else:
                return 0
        else:
            raise ValueError(
                f"Error: transpose columns/rows not supported on the report type {self.report_type}"
            )
```

</details>

<details>
<summary>LayoutREST.get_skip — utils/report_objects.py:1819–1829</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L1819-L1829)  
**Lines:** 1819–1829

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_skip(self):
        if "Layout:" in self.report_type:
            if "skip_empty" in json.loads(self.params):
                return json.loads(self.params)["skip_empty"]
            else:
                return 0
        else:
            raise ValueError(
                f"Error: skip empty not supported on the report type {self.report_type}"
            )
```

**Proposed**

```python
    def get_skip(self):
        if "Layout:" in self.report_type:
            parsed_params = json.loads(self.params)
            if "skip_empty" in parsed_params:
                return parsed_params["skip_empty"]
            else:
                return 0
        else:
            raise ValueError(
                f"Error: skip empty not supported on the report type {self.report_type}"
            )
```

</details>

<details>
<summary>GeneratorREST.get_generated_items — utils/report_objects.py:1853–1858</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L1853-L1858)  
**Lines:** 1853–1858

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_generated_items(self):
        if "generate_merge" in json.loads(self.params):
            return json.loads(self.params)["generate_merge"]
        else:
            return "add"
```

**Proposed**

```python
    def get_generated_items(self):
        parsed_params = json.loads(self.params)
        if "generate_merge" in parsed_params:
            return parsed_params["generate_merge"]
        else:
            return "add"
```

</details>

<details>
<summary>GeneratorREST.get_append_tags — utils/report_objects.py:1869–1874</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L1869-L1874)  
**Lines:** 1869–1874

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_append_tags(self):
        if "generate_appendtags" in json.loads(self.params):
            return json.loads(self.params)["generate_appendtags"]
        else:
            return True
```

**Proposed**

```python
    def get_append_tags(self):
        parsed_params = json.loads(self.params)
        if "generate_appendtags" in parsed_params:
            return parsed_params["generate_appendtags"]
        else:
            return True
```

</details>

<details>
<summary>panelREST.get_panel_style — utils/report_objects.py:1899–1904</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L1899-L1904)  
**Lines:** 1899–1904

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_panel_style(self):
        if "style" in json.loads(self.params):
            return json.loads(self.params)["style"]
        else:
            return ""
```

**Proposed**

```python
    def get_panel_style(self):
        parsed_params = json.loads(self.params)
        if "style" in parsed_params:
            return parsed_params["style"]
        else:
            return ""
```

</details>

<details>
<summary>panelREST.get_items_as_link — utils/report_objects.py:1922–1927</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L1922-L1927)  
**Lines:** 1922–1927

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_items_as_link(self):
        if "items_as_links" in json.loads(self.params):
            return json.loads(self.params)["items_as_links"]
        else:
            return 0
```

**Proposed**

```python
    def get_items_as_link(self):
        parsed_params = json.loads(self.params)
        if "items_as_links" in parsed_params:
            return parsed_params["items_as_links"]
        else:
            return 0
```

</details>

<details>
<summary>boxREST.get_children_layout — utils/report_objects.py:1945–1950</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L1945-L1950)  
**Lines:** 1945–1950

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_children_layout(self):
        if "boxes" in json.loads(self.params):
            return json.loads(self.params)["boxes"]
        else:
            return {}
```

**Proposed**

```python
    def get_children_layout(self):
        parsed_params = json.loads(self.params)
        if "boxes" in parsed_params:
            return parsed_params["boxes"]
        else:
            return {}
```

</details>

<details>
<summary>carouselREST.get_animated — utils/report_objects.py:2010–2015</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L2010-L2015)  
**Lines:** 2010–2015

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_animated(self):
        if "animate" in json.loads(self.params):
            return json.loads(self.params)["animate"]
        else:
            return 0
```

**Proposed**

```python
    def get_animated(self):
        parsed_params = json.loads(self.params)
        if "animate" in parsed_params:
            return parsed_params["animate"]
        else:
            return 0
```

</details>

<details>
<summary>carouselREST.get_slide_dots — utils/report_objects.py:2024–2029</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L2024-L2029)  
**Lines:** 2024–2029

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_slide_dots(self):
        if "maxdots" in json.loads(self.params):
            return json.loads(self.params)["maxdots"]
        else:
            return 20
```

**Proposed**

```python
    def get_slide_dots(self):
        parsed_params = json.loads(self.params)
        if "maxdots" in parsed_params:
            return parsed_params["maxdots"]
        else:
            return 20
```

</details>

<details>
<summary>sliderREST.get_map_to_slider — utils/report_objects.py:2045–2053</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L2045-L2053)  
**Lines:** 2045–2053

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_map_to_slider(self):
        slider = []
        if "slider_tags" in json.loads(self.params):
            for v in split_quoted_string_list(json.loads(self.params)["slider_tags"]):
                slider.append(v)
            return slider
        else:
            return []
```

**Proposed**

```python
    def get_map_to_slider(self):
        slider = []
        parsed_params = json.loads(self.params)
        if "slider_tags" in parsed_params:
            for v in split_quoted_string_list(parsed_params["slider_tags"]):
                slider.append(v)
            return slider
        else:
            return []
```

</details>

<details>
<summary>iteratorREST.get_iteration_tags — utils/report_objects.py:2124–2135</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L2124-L2135)  
**Lines:** 2124–2135

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_iteration_tags(self):
        it_tags = []
        if "tag" in json.loads(self.params):
            it_tags.append(json.loads(self.params)["tag"])
        else:
            it_tags.append("")
        if "secondary_tag" in json.loads(self.params):
            it_tags.append(json.loads(self.params)["secondary_tag"])
        else:
            it_tags.append("")
        return it_tags
```

**Proposed**

```python
    def get_iteration_tags(self):
        it_tags = []
        parsed_params = json.loads(self.params)
        if "tag" in parsed_params:
            it_tags.append(parsed_params["tag"])
        else:
            it_tags.append("")
        if "secondary_tag" in parsed_params:
            it_tags.append(parsed_params["secondary_tag"])
        else:
            it_tags.append("")
        return it_tags
```

</details>

<details>
<summary>iteratorREST.get_sort_tag — utils/report_objects.py:2153–2164</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L2153-L2164)  
**Lines:** 2153–2164

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_sort_tag(self):
        sort_int = []
        if "sort" in json.loads(self.params):
            sort_int.append(json.loads(self.params)["sort"])
        else:
            sort_int.append(True)
        if "reverse_sort" in json.loads(self.params):
            sort_int.append(json.loads(self.params)["reverse_sort"])
        else:
            sort_int.append(False)
        return sort_int
```

**Proposed**

```python
    def get_sort_tag(self):
        sort_int = []
        parsed_params = json.loads(self.params)
        if "sort" in parsed_params:
            sort_int.append(parsed_params["sort"])
        else:
            sort_int.append(True)
        if "reverse_sort" in parsed_params:
            sort_int.append(parsed_params["reverse_sort"])
        else:
            sort_int.append(False)
        return sort_int
```

</details>

<details>
<summary>tocREST.get_toc — utils/report_objects.py:2199–2215</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L2199-L2215)  
**Lines:** 2199–2215

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_toc(self):
        if (
            ("TOCitems" in json.loads(self.params))
            and ("TOCfigures" in json.loads(self.params))
            and ("TOCtables" in json.loads(self.params))
        ):
            if json.loads(self.params)["TOCfigures"] == 1:
                return "figure"
            elif json.loads(self.params)["TOCtables"] == 1:
                return "table"
            elif json.loads(self.params)["TOCitems"] == 1:
                return "toc"
            else:
                return None
        else:
            return None
```

**Proposed**

```python
    def get_toc(self):
        parsed_params = json.loads(self.params)
        if (
            ("TOCitems" in parsed_params)
            and ("TOCfigures" in parsed_params)
            and ("TOCtables" in parsed_params)
        ):
            if parsed_params["TOCfigures"] == 1:
                return "figure"
            elif parsed_params["TOCtables"] == 1:
                return "table"
            elif parsed_params["TOCitems"] == 1:
                return "toc"
            else:
                return None
        else:
            return None
```

</details>

<details>
<summary>reportlinkREST.get_report_link — utils/report_objects.py:2244–2252</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L2244-L2252)  
**Lines:** 2244–2252

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_report_link(self):
        if "report_guid" in json.loads(self.params):
            if json.loads(self.params)["report_guid"] == "":
                return None
            else:
                return json.loads(self.params)["report_guid"]
        else:
            return None
```

**Proposed**

```python
    def get_report_link(self):
        parsed_params = json.loads(self.params)
        if "report_guid" in parsed_params:
            if parsed_params["report_guid"] == "":
                return None
            else:
                return parsed_params["report_guid"]
        else:
            return None
```

</details>

<details>
<summary>tablemergeREST.get_merging_param — utils/report_objects.py:2275–2280</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L2275-L2280)  
**Lines:** 2275–2280

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_merging_param(self):
        if "merge_params" in json.loads(self.params):
            if "merge_type" in json.loads(self.params)["merge_params"]:
                return json.loads(self.params)["merge_params"]["merge_type"]
        return "row"
```

**Proposed**

```python
    def get_merging_param(self):
        parsed_params = json.loads(self.params)
        if "merge_params" in parsed_params:
            if "merge_type" in parsed_params["merge_params"]:
                return parsed_params["merge_params"]["merge_type"]
        return "row"
```

</details>

<details>
<summary>tablemergeREST.get_table_name — utils/report_objects.py:2293–2298</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L2293-L2298)  
**Lines:** 2293–2298

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_table_name(self):
        if "merge_params" in json.loads(self.params):
            if "table_name" in json.loads(self.params)["merge_params"]:
                return json.loads(self.params)["merge_params"]["table_name"]
        return ""
```

**Proposed**

```python
    def get_table_name(self):
        parsed_params = json.loads(self.params)
        if "merge_params" in parsed_params:
            if "table_name" in parsed_params["merge_params"]:
                return parsed_params["merge_params"]["table_name"]
        return ""
```

</details>

<details>
<summary>tablemergeREST.get_sources — utils/report_objects.py:2309–2317</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L2309-L2317)  
**Lines:** 2309–2317

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_sources(self):
        if "merge_params" in json.loads(self.params):
            if "source_rows" in json.loads(self.params)["merge_params"]:
                sources = []
                for i in shlex.split(json.loads(self.params)["merge_params"]["source_rows"]):
                    sources.append(i.replace(",", ""))
                return sources
        return ["*|duplicate"]
```

**Proposed**

```python
    def get_sources(self):
        parsed_params = json.loads(self.params)
        if "merge_params" in parsed_params:
            if "source_rows" in parsed_params["merge_params"]:
                sources = []
                for i in shlex.split(parsed_params["merge_params"]["source_rows"]):
                    sources.append(i.replace(",", ""))
                return sources
        return ["*|duplicate"]
```

</details>

<details>
<summary>tablemergeREST.get_rename_tag — utils/report_objects.py:2354–2359</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L2354-L2359)  
**Lines:** 2354–2359

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_rename_tag(self):
        if "merge_params" in json.loads(self.params):
            if "collision_tag" in json.loads(self.params)["merge_params"]:
                return json.loads(self.params)["merge_params"]["collision_tag"]
        return ""
```

**Proposed**

```python
    def get_rename_tag(self):
        parsed_params = json.loads(self.params)
        if "merge_params" in parsed_params:
            if "collision_tag" in parsed_params["merge_params"]:
                return parsed_params["merge_params"]["collision_tag"]
        return ""
```

</details>

<details>
<summary>tablemergeREST.get_use_labels — utils/report_objects.py:2370–2375</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L2370-L2375)  
**Lines:** 2370–2375

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_use_labels(self):
        if "merge_params" in json.loads(self.params):
            if "column_labels_as_ids" in json.loads(self.params)["merge_params"]:
                return json.loads(self.params)["merge_params"]["column_labels_as_ids"]
        return 1
```

**Proposed**

```python
    def get_use_labels(self):
        parsed_params = json.loads(self.params)
        if "merge_params" in parsed_params:
            if "column_labels_as_ids" in parsed_params["merge_params"]:
                return parsed_params["merge_params"]["column_labels_as_ids"]
        return 1
```

</details>

<details>
<summary>tablemergeREST.get_use_ids — utils/report_objects.py:2388–2396</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L2388-L2396)  
**Lines:** 2388–2396

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_use_ids(self):
        if "merge_params" in json.loads(self.params):
            if "column_labels_as_ids" in json.loads(self.params)["merge_params"]:
                if json.loads(self.params)["merge_params"]["column_labels_as_ids"] == 1:
                    return ""
            if "column_id_row" in json.loads(self.params)["merge_params"]:
                return json.loads(self.params)["merge_params"]["column_id_row"]
        return ""
```

**Proposed**

```python
    def get_use_ids(self):
        parsed_params = json.loads(self.params)
        if "merge_params" in parsed_params:
            if "column_labels_as_ids" in parsed_params["merge_params"]:
                if parsed_params["merge_params"]["column_labels_as_ids"] == 1:
                    return ""
            if "column_id_row" in parsed_params["merge_params"]:
                return parsed_params["merge_params"]["column_id_row"]
        return ""
```

</details>

<details>
<summary>tablemergeREST.get_id_selection — utils/report_objects.py:2418–2423</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L2418-L2423)  
**Lines:** 2418–2423

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_id_selection(self):
        if "merge_params" in json.loads(self.params):
            if "column_merge" in json.loads(self.params)["merge_params"]:
                return json.loads(self.params)["merge_params"]["column_merge"]
        return "all"
```

**Proposed**

```python
    def get_id_selection(self):
        parsed_params = json.loads(self.params)
        if "merge_params" in parsed_params:
            if "column_merge" in parsed_params["merge_params"]:
                return parsed_params["merge_params"]["column_merge"]
        return "all"
```

</details>

<details>
<summary>tablemergeREST.get_ids — utils/report_objects.py:2436–2450</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L2436-L2450)  
**Lines:** 2436–2450

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_ids(self):
        if "merge_params" in json.loads(self.params):
            if "column_merge" in json.loads(self.params)["merge_params"]:
                if json.loads(self.params)["merge_params"]["column_merge"] != "select":
                    # grayed out if ID selection is not set to Select Specific IDs
                    return []
            if "selected_column_ids" in json.loads(self.params)["merge_params"]:
                values = json.loads(self.params)["merge_params"]["selected_column_ids"]
                outvalue = []
                for v in shlex.split(values):
                    outvalue.append(int(v.replace(",", "")))
                return outvalue
            else:
                return []
```

**Proposed**

```python
    def get_ids(self):
        parsed_params = json.loads(self.params)
        if "merge_params" in parsed_params:
            if "column_merge" in parsed_params["merge_params"]:
                if parsed_params["merge_params"]["column_merge"] != "select":
                    # grayed out if ID selection is not set to Select Specific IDs
                    return []
            if "selected_column_ids" in parsed_params["merge_params"]:
                values = parsed_params["merge_params"]["selected_column_ids"]
                outvalue = []
                for v in shlex.split(values):
                    outvalue.append(int(v.replace(",", "")))
                return outvalue
            else:
                return []
```

</details>

<details>
<summary>tablemergeREST.add_ids — utils/report_objects.py:2475–2500</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L2475-L2500)  
**Lines:** 2475–2500

The shallow dictionary copy preserves the distinction between original JSON and the locally inserted merge_params key. Existing malformed-input errors are retained.

**Current**

```python
    def add_ids(self, value=None):
        if value is None:
            value = []
        d = json.loads(self.params)
        if "merge_params" not in d:
            d["merge_params"] = {}
        if json.loads(self.params)["merge_params"]["column_merge"] != "select":
            # grayed out if ID selection is not set to Select Specific IDs
            if d["merge_params"]["merge_type"] == "row":
                raise ValueError(
                    "Error: can not add column IDs if the Column ID selection is not set to specific IDs"
                )
            if d["merge_params"]["merge_type"] == "column":
                raise ValueError(
                    "Error: can not add row IDs if the Row ID selection is not set to specific IDs"
                )
        if type(value) is not list:
            raise ValueError("Error: input should be a list")
        if len([x for x in value if type(x) == int]) != len(value):
            raise ValueError("Error: input should be a list of integers only")
        d["merge_params"]["selected_column_ids"] = ", ".join(
            [d["merge_params"]["selected_column_ids"], ", ".join(repr(x) for x in value)]
        )
        self.params = json.dumps(d)
        return
```

**Proposed**

```python
    def add_ids(self, value=None):
        if value is None:
            value = []
        parsed_params = json.loads(self.params)
        d = parsed_params.copy() if isinstance(parsed_params, dict) else parsed_params
        if "merge_params" not in d:
            d["merge_params"] = {}
        if parsed_params["merge_params"]["column_merge"] != "select":
            # grayed out if ID selection is not set to Select Specific IDs
            if d["merge_params"]["merge_type"] == "row":
                raise ValueError(
                    "Error: can not add column IDs if the Column ID selection is not set to specific IDs"
                )
            if d["merge_params"]["merge_type"] == "column":
                raise ValueError(
                    "Error: can not add row IDs if the Row ID selection is not set to specific IDs"
                )
        if type(value) is not list:
            raise ValueError("Error: input should be a list")
        if len([x for x in value if type(x) == int]) != len(value):
            raise ValueError("Error: input should be a list of integers only")
        d["merge_params"]["selected_column_ids"] = ", ".join(
            [d["merge_params"]["selected_column_ids"], ", ".join(repr(x) for x in value)]
        )
        self.params = json.dumps(d)
        return
```

</details>

<details>
<summary>tablemergeREST.get_unknown_value — utils/report_objects.py:2501–2506</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L2501-L2506)  
**Lines:** 2501–2506

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_unknown_value(self):
        if "merge_params" in json.loads(self.params):
            if "unknown_value" in json.loads(self.params)["merge_params"]:
                return json.loads(self.params)["merge_params"]["unknown_value"]
        return "nan"
```

**Proposed**

```python
    def get_unknown_value(self):
        parsed_params = json.loads(self.params)
        if "merge_params" in parsed_params:
            if "unknown_value" in parsed_params["merge_params"]:
                return parsed_params["merge_params"]["unknown_value"]
        return "nan"
```

</details>

<details>
<summary>tablemergeREST.get_table_transpose — utils/report_objects.py:2517–2522</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L2517-L2522)  
**Lines:** 2517–2522

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_table_transpose(self):
        if "merge_params" in json.loads(self.params):
            if "transpose_output" in json.loads(self.params)["merge_params"]:
                return json.loads(self.params)["merge_params"]["transpose_output"]
        return 0
```

**Proposed**

```python
    def get_table_transpose(self):
        parsed_params = json.loads(self.params)
        if "merge_params" in parsed_params:
            if "transpose_output" in parsed_params["merge_params"]:
                return parsed_params["merge_params"]["transpose_output"]
        return 0
```

</details>

<details>
<summary>tablemergeREST.get_numeric_output — utils/report_objects.py:2535–2540</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L2535-L2540)  
**Lines:** 2535–2540

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_numeric_output(self):
        if "merge_params" in json.loads(self.params):
            if "force_numeric" in json.loads(self.params)["merge_params"]:
                return json.loads(self.params)["merge_params"]["force_numeric"]
        return 0
```

**Proposed**

```python
    def get_numeric_output(self):
        parsed_params = json.loads(self.params)
        if "merge_params" in parsed_params:
            if "force_numeric" in parsed_params["merge_params"]:
                return parsed_params["merge_params"]["force_numeric"]
        return 0
```

</details>

<details>
<summary>tablereduceREST.get_reduce_param — utils/report_objects.py:2560–2565</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L2560-L2565)  
**Lines:** 2560–2565

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_reduce_param(self):
        if "reduce_params" in json.loads(self.params):
            if "reduce_type" in json.loads(self.params)["reduce_params"]:
                return json.loads(self.params)["reduce_params"]["reduce_type"]
        return "row"
```

**Proposed**

```python
    def get_reduce_param(self):
        parsed_params = json.loads(self.params)
        if "reduce_params" in parsed_params:
            if "reduce_type" in parsed_params["reduce_params"]:
                return parsed_params["reduce_params"]["reduce_type"]
        return "row"
```

</details>

<details>
<summary>tablereduceREST.get_table_name — utils/report_objects.py:2578–2583</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L2578-L2583)  
**Lines:** 2578–2583

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_table_name(self):
        if "reduce_params" in json.loads(self.params):
            if "table_name" in json.loads(self.params)["reduce_params"]:
                return json.loads(self.params)["reduce_params"]["table_name"]
        return ""
```

**Proposed**

```python
    def get_table_name(self):
        parsed_params = json.loads(self.params)
        if "reduce_params" in parsed_params:
            if "table_name" in parsed_params["reduce_params"]:
                return parsed_params["reduce_params"]["table_name"]
        return ""
```

</details>

<details>
<summary>tablereduceREST.get_operations — utils/report_objects.py:2594–2599</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L2594-L2599)  
**Lines:** 2594–2599

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_operations(self):
        if "reduce_params" in json.loads(self.params):
            if "operations" in json.loads(self.params)["reduce_params"]:
                return json.loads(self.params)["reduce_params"]["operations"]
        return []
```

**Proposed**

```python
    def get_operations(self):
        parsed_params = json.loads(self.params)
        if "reduce_params" in parsed_params:
            if "operations" in parsed_params["reduce_params"]:
                return parsed_params["reduce_params"]["operations"]
        return []
```

</details>

<details>
<summary>tablereduceREST.get_table_transpose — utils/report_objects.py:2693–2698</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L2693-L2698)  
**Lines:** 2693–2698

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_table_transpose(self):
        if "reduce_params" in json.loads(self.params):
            if "transpose_output" in json.loads(self.params)["reduce_params"]:
                return json.loads(self.params)["reduce_params"]["transpose_output"]
        return 0
```

**Proposed**

```python
    def get_table_transpose(self):
        parsed_params = json.loads(self.params)
        if "reduce_params" in parsed_params:
            if "transpose_output" in parsed_params["reduce_params"]:
                return parsed_params["reduce_params"]["transpose_output"]
        return 0
```

</details>

<details>
<summary>tablereduceREST.get_numeric_output — utils/report_objects.py:2711–2716</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L2711-L2716)  
**Lines:** 2711–2716

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_numeric_output(self):
        if "reduce_params" in json.loads(self.params):
            if "force_numeric" in json.loads(self.params)["reduce_params"]:
                return json.loads(self.params)["reduce_params"]["force_numeric"]
        return 0
```

**Proposed**

```python
    def get_numeric_output(self):
        parsed_params = json.loads(self.params)
        if "reduce_params" in parsed_params:
            if "force_numeric" in parsed_params["reduce_params"]:
                return parsed_params["reduce_params"]["force_numeric"]
        return 0
```

</details>

<details>
<summary>tablerowcolumnfilterREST.get_table_name — utils/report_objects.py:2893–2898</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L2893-L2898)  
**Lines:** 2893–2898

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_table_name(self):
        if "table_name" in json.loads(self.params):
            return json.loads(self.params)["table_name"]
        else:
            return ""
```

**Proposed**

```python
    def get_table_name(self):
        parsed_params = json.loads(self.params)
        if "table_name" in parsed_params:
            return parsed_params["table_name"]
        else:
            return ""
```

</details>

<details>
<summary>tablerowcolumnfilterREST.get_filter_rows — utils/report_objects.py:2907–2915</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L2907-L2915)  
**Lines:** 2907–2915

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_filter_rows(self):
        if "select_rows" in json.loads(self.params):
            out = []
            for i in shlex.split(json.loads(self.params)["select_rows"]):
                out.append(i.replace(",", ""))
            return out
        else:
            return ["*"]
```

**Proposed**

```python
    def get_filter_rows(self):
        parsed_params = json.loads(self.params)
        if "select_rows" in parsed_params:
            out = []
            for i in shlex.split(parsed_params["select_rows"]):
                out.append(i.replace(",", ""))
            return out
        else:
            return ["*"]
```

</details>

<details>
<summary>tablerowcolumnfilterREST.get_filter_columns — utils/report_objects.py:2940–2948</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L2940-L2948)  
**Lines:** 2940–2948

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_filter_columns(self):
        if "select_columns" in json.loads(self.params):
            out = []
            for i in shlex.split(json.loads(self.params)["select_columns"]):
                out.append(i.replace(",", ""))
            return out
        else:
            return ["*"]
```

**Proposed**

```python
    def get_filter_columns(self):
        parsed_params = json.loads(self.params)
        if "select_columns" in parsed_params:
            out = []
            for i in shlex.split(parsed_params["select_columns"]):
                out.append(i.replace(",", ""))
            return out
        else:
            return ["*"]
```

</details>

<details>
<summary>tablerowcolumnfilterREST.get_invert — utils/report_objects.py:2973–2978</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L2973-L2978)  
**Lines:** 2973–2978

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_invert(self):
        if "invert" in json.loads(self.params):
            return json.loads(self.params)["invert"]
        else:
            return 0
```

**Proposed**

```python
    def get_invert(self):
        parsed_params = json.loads(self.params)
        if "invert" in parsed_params:
            return parsed_params["invert"]
        else:
            return 0
```

</details>

<details>
<summary>tablerowcolumnfilterREST.get_sort — utils/report_objects.py:2989–2994</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L2989-L2994)  
**Lines:** 2989–2994

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_sort(self):
        if "reorder" in json.loads(self.params):
            return json.loads(self.params)["reorder"]
        else:
            return 0
```

**Proposed**

```python
    def get_sort(self):
        parsed_params = json.loads(self.params)
        if "reorder" in parsed_params:
            return parsed_params["reorder"]
        else:
            return 0
```

</details>

<details>
<summary>tablerowcolumnfilterREST.get_table_transpose — utils/report_objects.py:3007–3012</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L3007-L3012)  
**Lines:** 3007–3012

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_table_transpose(self):
        if "transpose" in json.loads(self.params):
            return json.loads(self.params)["transpose"]
        else:
            return 0
```

**Proposed**

```python
    def get_table_transpose(self):
        parsed_params = json.loads(self.params)
        if "transpose" in parsed_params:
            return parsed_params["transpose"]
        else:
            return 0
```

</details>

<details>
<summary>tablevaluefilterREST.get_table_name — utils/report_objects.py:3030–3035</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L3030-L3035)  
**Lines:** 3030–3035

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_table_name(self):
        if "table_name" in json.loads(self.params):
            return json.loads(self.params)["table_name"]
        else:
            return ""
```

**Proposed**

```python
    def get_table_name(self):
        parsed_params = json.loads(self.params)
        if "table_name" in parsed_params:
            return parsed_params["table_name"]
        else:
            return ""
```

</details>

<details>
<summary>tablevaluefilterREST.get_filter_by — utils/report_objects.py:3044–3055</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L3044-L3055)  
**Lines:** 3044–3055

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_filter_by(self):
        out = []
        if "row_column" in json.loads(self.params):
            out.append(json.loads(self.params)["row_column"])
        else:
            out.append("column")
        if "column_name" in json.loads(self.params):
            out.append(json.loads(self.params)["column_name"])
        else:
            out.append("0")
        return out
```

**Proposed**

```python
    def get_filter_by(self):
        out = []
        parsed_params = json.loads(self.params)
        if "row_column" in parsed_params:
            out.append(parsed_params["row_column"])
        else:
            out.append("column")
        if "column_name" in parsed_params:
            out.append(parsed_params["column_name"])
        else:
            out.append("0")
        return out
```

</details>

<details>
<summary>tablevaluefilterREST.get_filter_value — utils/report_objects.py:3073–3112</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L3073-L3112)  
**Lines:** 3073–3112

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_filter_value(self):
        if "filter" in json.loads(self.params):
            if json.loads(self.params)["filter"] == "range":
                if "range_min" in json.loads(self.params):
                    return [
                        "range",
                        json.loads(self.params)["range_min"],
                        json.loads(self.params)["range_max"],
                    ]
                else:
                    return ["range", "", ""]
            elif json.loads(self.params)["filter"] == "specific":
                if "specific_values" in json.loads(self.params):
                    values = []
                    for i in shlex.split(json.loads(self.params)["specific_values"]):
                        values.append(i.replace(",", ""))
                    return ["specific", values]
                else:
                    return ["specific", ["*"]]
            elif json.loads(self.params)["filter"] == "top_percent":
                if "percent" in json.loads(self.params):
                    return ["top_percent", float(json.loads(self.params)["percent"])]
                else:
                    return ["top_percent", 10.0]
            elif json.loads(self.params)["filter"] == "top_count":
                if "count" in json.loads(self.params):
                    return ["top_count", int(json.loads(self.params)["count"])]
                else:
                    return ["top_count", 10]
            elif json.loads(self.params)["filter"] == "bot_percent":
                if "percent" in json.loads(self.params):
                    return ["bot_percent", float(json.loads(self.params)["percent"])]
                else:
                    return ["bot_percent", 10.0]
            elif json.loads(self.params)["filter"] == "bot_count":
                if "count" in json.loads(self.params):
                    return ["bot_count", int(json.loads(self.params)["count"])]
                else:
                    return ["bot_count", 10]
```

**Proposed**

```python
    def get_filter_value(self):
        parsed_params = json.loads(self.params)
        if "filter" in parsed_params:
            if parsed_params["filter"] == "range":
                if "range_min" in parsed_params:
                    return [
                        "range",
                        parsed_params["range_min"],
                        parsed_params["range_max"],
                    ]
                else:
                    return ["range", "", ""]
            elif parsed_params["filter"] == "specific":
                if "specific_values" in parsed_params:
                    values = []
                    for i in shlex.split(parsed_params["specific_values"]):
                        values.append(i.replace(",", ""))
                    return ["specific", values]
                else:
                    return ["specific", ["*"]]
            elif parsed_params["filter"] == "top_percent":
                if "percent" in parsed_params:
                    return ["top_percent", float(parsed_params["percent"])]
                else:
                    return ["top_percent", 10.0]
            elif parsed_params["filter"] == "top_count":
                if "count" in parsed_params:
                    return ["top_count", int(parsed_params["count"])]
                else:
                    return ["top_count", 10]
            elif parsed_params["filter"] == "bot_percent":
                if "percent" in parsed_params:
                    return ["bot_percent", float(parsed_params["percent"])]
                else:
                    return ["bot_percent", 10.0]
            elif parsed_params["filter"] == "bot_count":
                if "count" in parsed_params:
                    return ["bot_count", int(parsed_params["count"])]
                else:
                    return ["bot_count", 10]
```

</details>

<details>
<summary>tablevaluefilterREST.get_invert_filter — utils/report_objects.py:3189–3194</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L3189-L3194)  
**Lines:** 3189–3194

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_invert_filter(self):
        if "invert" in json.loads(self.params):
            return json.loads(self.params)["invert"]
        else:
            return 0
```

**Proposed**

```python
    def get_invert_filter(self):
        parsed_params = json.loads(self.params)
        if "invert" in parsed_params:
            return parsed_params["invert"]
        else:
            return 0
```

</details>

<details>
<summary>tablevaluefilterREST.get_values_as_dates — utils/report_objects.py:3205–3210</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L3205-L3210)  
**Lines:** 3205–3210

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_values_as_dates(self):
        if "values_as_dates" in json.loads(self.params):
            return json.loads(self.params)["values_as_dates"]
        else:
            return 0
```

**Proposed**

```python
    def get_values_as_dates(self):
        parsed_params = json.loads(self.params)
        if "values_as_dates" in parsed_params:
            return parsed_params["values_as_dates"]
        else:
            return 0
```

</details>

<details>
<summary>tablesortfilterREST.get_table_name — utils/report_objects.py:3228–3233</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L3228-L3233)  
**Lines:** 3228–3233

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_table_name(self):
        if "table_name" in json.loads(self.params):
            return json.loads(self.params)["table_name"]
        else:
            return "sorted table"
```

**Proposed**

```python
    def get_table_name(self):
        parsed_params = json.loads(self.params)
        if "table_name" in parsed_params:
            return parsed_params["table_name"]
        else:
            return "sorted table"
```

</details>

<details>
<summary>tablesortfilterREST.get_sort_rows — utils/report_objects.py:3242–3247</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L3242-L3247)  
**Lines:** 3242–3247

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_sort_rows(self):
        if "sort_rows" in json.loads(self.params):
            return json.loads(self.params)["sort_rows"]
        else:
            return []
```

**Proposed**

```python
    def get_sort_rows(self):
        parsed_params = json.loads(self.params)
        if "sort_rows" in parsed_params:
            return parsed_params["sort_rows"]
        else:
            return []
```

</details>

<details>
<summary>tablesortfilterREST.get_sort_columns — utils/report_objects.py:3278–3283</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L3278-L3283)  
**Lines:** 3278–3283

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_sort_columns(self):
        if "sort_columns" in json.loads(self.params):
            return json.loads(self.params)["sort_columns"]
        else:
            return []
```

**Proposed**

```python
    def get_sort_columns(self):
        parsed_params = json.loads(self.params)
        if "sort_columns" in parsed_params:
            return parsed_params["sort_columns"]
        else:
            return []
```

</details>

<details>
<summary>sqlqueriesREST.get_db_type — utils/report_objects.py:3378–3383</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L3378-L3383)  
**Lines:** 3378–3383

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_db_type(self):
        if "typedb" in json.loads(self.params):
            return json.loads(self.params)["typedb"]
        else:
            return "SQLite"
```

**Proposed**

```python
    def get_db_type(self):
        parsed_params = json.loads(self.params)
        if "typedb" in parsed_params:
            return parsed_params["typedb"]
        else:
            return "SQLite"
```

</details>

<details>
<summary>sqlqueriesREST.get_sqlite_name — utils/report_objects.py:3394–3399</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L3394-L3399)  
**Lines:** 3394–3399

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_sqlite_name(self):
        if "sqldb" in json.loads(self.params):
            return json.loads(self.params)["sqldb"]
        else:
            return ""
```

**Proposed**

```python
    def get_sqlite_name(self):
        parsed_params = json.loads(self.params)
        if "sqldb" in parsed_params:
            return parsed_params["sqldb"]
        else:
            return ""
```

</details>

<details>
<summary>sqlqueriesREST.get_postgre — utils/report_objects.py:3412–3444</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L3412-L3444)  
**Lines:** 3412–3444

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_postgre(self):
        out = {}
        if "sqldb" in json.loads(self.params):
            if "sqldb" in json.loads(self.params):
                out["database"] = json.loads(self.params)["sqldb"]
            else:
                out["database"] = ""
            if "hostsqldb" in json.loads(self.params):
                out["hostname"] = json.loads(self.params)["hostsqldb"]
            else:
                out["hostname"] = ""
            if "portsqldb" in json.loads(self.params):
                out["port"] = str(json.loads(self.params)["portsqldb"])
            else:
                out["port"] = ""
            if "usrsqldb" in json.loads(self.params):
                out["username"] = json.loads(self.params)["usrsqldb"]
            else:
                out["username"]
            if "pswsqldb" in json.loads(self.params):
                out["password"] = json.loads(self.params)["pswsqldb"]
            else:
                out["password"] = ""  # nosec B259
        else:
            out = {
                "database": "",
                "hostname": "",
                "port": "",
                "username": "",
                "password": "",
            }  # nosec B105
        return out
```

**Proposed**

```python
    def get_postgre(self):
        out = {}
        parsed_params = json.loads(self.params)
        if "sqldb" in parsed_params:
            if "sqldb" in parsed_params:
                out["database"] = parsed_params["sqldb"]
            else:
                out["database"] = ""
            if "hostsqldb" in parsed_params:
                out["hostname"] = parsed_params["hostsqldb"]
            else:
                out["hostname"] = ""
            if "portsqldb" in parsed_params:
                out["port"] = str(parsed_params["portsqldb"])
            else:
                out["port"] = ""
            if "usrsqldb" in parsed_params:
                out["username"] = parsed_params["usrsqldb"]
            else:
                out["username"]
            if "pswsqldb" in parsed_params:
                out["password"] = parsed_params["pswsqldb"]
            else:
                out["password"] = ""  # nosec B259
        else:
            out = {
                "database": "",
                "hostname": "",
                "port": "",
                "username": "",
                "password": "",
            }  # nosec B105
        return out
```

</details>

<details>
<summary>sqlqueriesREST.get_query — utils/report_objects.py:3484–3489</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L3484-L3489)  
**Lines:** 3484–3489

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_query(self):
        if "sqlquery" in json.loads(self.params):
            return json.loads(self.params)["sqlquery"]
        else:
            return ""
```

**Proposed**

```python
    def get_query(self):
        parsed_params = json.loads(self.params)
        if "sqlquery" in parsed_params:
            return parsed_params["sqlquery"]
        else:
            return ""
```

</details>

<details>
<summary>statisticalREST.get_analysis_type — utils/report_objects.py:3798–3805</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L3798-L3805)  
**Lines:** 3798–3805

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_analysis_type(self):
        if (
            "stats_params" in json.loads(self.params)
            and "analysis_type" in json.loads(self.params)["stats_params"]
        ):
            return json.loads(self.params)["stats_params"]["analysis_type"]
        return ""
```

**Proposed**

```python
    def get_analysis_type(self):
        parsed_params = json.loads(self.params)
        if (
            "stats_params" in parsed_params
            and "analysis_type" in parsed_params["stats_params"]
        ):
            return parsed_params["stats_params"]["analysis_type"]
        return ""
```

</details>

<details>
<summary>statisticalREST.get_table_name — utils/report_objects.py:3823–3830</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L3823-L3830)  
**Lines:** 3823–3830

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_table_name(self):
        if (
            "stats_params" in json.loads(self.params)
            and "table_name" in json.loads(self.params)["stats_params"]
        ):
            return json.loads(self.params)["stats_params"]["table_name"]
        return ""
```

**Proposed**

```python
    def get_table_name(self):
        parsed_params = json.loads(self.params)
        if (
            "stats_params" in parsed_params
            and "table_name" in parsed_params["stats_params"]
        ):
            return parsed_params["stats_params"]["table_name"]
        return ""
```

</details>

<details>
<summary>statisticalREST.get_tree_name — utils/report_objects.py:3840–3847</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L3840-L3847)  
**Lines:** 3840–3847

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_tree_name(self):
        if (
            "stats_params" in json.loads(self.params)
            and "tree_name" in json.loads(self.params)["stats_params"]
        ):
            return json.loads(self.params)["stats_params"]["tree_name"]
        return ""
```

**Proposed**

```python
    def get_tree_name(self):
        parsed_params = json.loads(self.params)
        if (
            "stats_params" in parsed_params
            and "tree_name" in parsed_params["stats_params"]
        ):
            return parsed_params["stats_params"]["tree_name"]
        return ""
```

</details>

<details>
<summary>statisticalREST.get_predictor_variables — utils/report_objects.py:3857–3864</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L3857-L3864)  
**Lines:** 3857–3864

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_predictor_variables(self):
        if (
            "stats_params" in json.loads(self.params)
            and "predictor_variables" in json.loads(self.params)["stats_params"]
        ):
            return json.loads(json.loads(self.params)["stats_params"]["predictor_variables"])
        return []
```

**Proposed**

```python
    def get_predictor_variables(self):
        parsed_params = json.loads(self.params)
        if (
            "stats_params" in parsed_params
            and "predictor_variables" in parsed_params["stats_params"]
        ):
            return json.loads(parsed_params["stats_params"]["predictor_variables"])
        return []
```

</details>

<details>
<summary>statisticalREST.get_response_variables — utils/report_objects.py:3888–3895</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L3888-L3895)  
**Lines:** 3888–3895

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_response_variables(self):
        if (
            "stats_params" in json.loads(self.params)
            and "response_variables" in json.loads(self.params)["stats_params"]
        ):
            return json.loads(json.loads(self.params)["stats_params"]["response_variables"])
        return []
```

**Proposed**

```python
    def get_response_variables(self):
        parsed_params = json.loads(self.params)
        if (
            "stats_params" in parsed_params
            and "response_variables" in parsed_params["stats_params"]
        ):
            return json.loads(parsed_params["stats_params"]["response_variables"])
        return []
```

</details>

<details>
<summary>statisticalREST.get_analysis_params — utils/report_objects.py:3910–3917</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L3910-L3917)  
**Lines:** 3910–3917

The parse stays at the first existing parse statement, inside the same report-type branch where applicable.

**Current**

```python
    def get_analysis_params(self):
        if (
            "stats_params" in json.loads(self.params)
            and "analysis_parameters" in json.loads(self.params)["stats_params"]
        ):
            return json.loads(json.loads(self.params)["stats_params"]["analysis_parameters"])
        return []
```

**Proposed**

```python
    def get_analysis_params(self):
        parsed_params = json.loads(self.params)
        if (
            "stats_params" in parsed_params
            and "analysis_parameters" in parsed_params["stats_params"]
        ):
            return json.loads(parsed_params["stats_params"]["analysis_parameters"])
        return []
```

</details>

[Back to contents](#contents)

<a id="c02"></a>

## C02. Index templates once during REST JSON export

**Behavior-sensitive.** A full template-list scan is repeated for every exported node. A local GUID map reduces lookup work from O(nodes × available templates) to O(nodes + available templates).

**Compatibility:** The dictionary requires hashable GUIDs and reads them all before traversal. The existing scan can ignore unrelated objects with unhashable GUIDs, and later lookups can observe GUID mutations. An overridden `_build_template_data` also receives a dictionary instead of its previous list. The direct-call list fallback does not protect that override. Last-match duplicate handling, sibling ID assignment, and missing-node failures must remain unchanged.

<details>
<summary>utils/report_remote_server.py:1327–1345</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_remote_server.py#L1327-L1345)  
**Lines:** 1327–1345

**Current**

```python
    def get_templates_as_dict(self, root_guid):
        """
        Convert report templates rooted at the specified root_guid into a JSON-compatible dictionary.

        Parameters
        ----------
        root_guid : str
            The GUID of the root template to start the conversion.

        Returns
        -------
        dict
            A Python dictionary representation of the template hierarchy.
        """
        templates_data = {}
        templates = self.get_objects(objtype=report_objects.TemplateREST)
        template_guid_id_map = {root_guid: 0}
        self._build_template_data(root_guid, templates_data, templates, template_guid_id_map)
        return templates_data
```

**Alternative**

```python
    def get_templates_as_dict(self, root_guid):
        """
        Convert report templates rooted at the specified root_guid into a JSON-compatible dictionary.

        Parameters
        ----------
        root_guid : str
            The GUID of the root template to start the conversion.

        Returns
        -------
        dict
            A Python dictionary representation of the template hierarchy.
        """
        templates_data = {}
        templates = self.get_objects(objtype=report_objects.TemplateREST)
        templates_by_guid = {template.guid: template for template in templates}
        template_guid_id_map = {root_guid: 0}
        self._build_template_data(root_guid, templates_data, templates_by_guid, template_guid_id_map)
        return templates_data
```

</details>

<details>
<summary>utils/report_remote_server.py:1422–1455</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_remote_server.py#L1422-L1455)  
**Lines:** 1422–1455

**Current**

```python
    def _build_template_data(self, guid, templates_data, templates, template_guid_id_map):
        curr_template = None
        for template in templates:
            if template.guid == guid:
                curr_template = template

        curr_template_key = f"Template_{template_guid_id_map[curr_template.guid]}"
        templates_data[curr_template_key] = {}
        for field in JSON_ATTR_KEYS:
            value = getattr(curr_template, field, None)
            if value is None:
                continue
            templates_data[curr_template_key][field] = value

        templates_data[curr_template_key]["params"] = curr_template.get_params()
        templates_data[curr_template_key]["sort_selection"] = curr_template.get_sort_selection()
        if curr_template.parent is None:
            templates_data[curr_template_key]["parent"] = None
            templates_data[curr_template_key]["guid"] = str(uuid.uuid4())
        else:
            templates_data[curr_template_key]["parent"] = (
                f"Template_{template_guid_id_map[curr_template.parent]}"
            )

        templates_data[curr_template_key]["children"] = []
        children_guids = curr_template.children
        for child_guid in children_guids:
            curr_size = len(template_guid_id_map)
            template_guid_id_map[child_guid] = curr_size
            templates_data[curr_template_key]["children"].append(f"Template_{curr_size}")

        # Don't combine these 2 for loops, as we want to have consecutive IDs for children
        for child_guid in children_guids:
            self._build_template_data(child_guid, templates_data, templates, template_guid_id_map)
```

**Alternative**

```python
    def _build_template_data(self, guid, templates_data, templates, template_guid_id_map):
        if isinstance(templates, dict):
            curr_template = templates.get(guid)
        else:
            curr_template = None
            for template in templates:
                if template.guid == guid:
                    curr_template = template

        curr_template_key = f"Template_{template_guid_id_map[curr_template.guid]}"
        templates_data[curr_template_key] = {}
        for field in JSON_ATTR_KEYS:
            value = getattr(curr_template, field, None)
            if value is None:
                continue
            templates_data[curr_template_key][field] = value

        templates_data[curr_template_key]["params"] = curr_template.get_params()
        templates_data[curr_template_key]["sort_selection"] = curr_template.get_sort_selection()
        if curr_template.parent is None:
            templates_data[curr_template_key]["parent"] = None
            templates_data[curr_template_key]["guid"] = str(uuid.uuid4())
        else:
            templates_data[curr_template_key]["parent"] = (
                f"Template_{template_guid_id_map[curr_template.parent]}"
            )

        templates_data[curr_template_key]["children"] = []
        children_guids = curr_template.children
        for child_guid in children_guids:
            curr_size = len(template_guid_id_map)
            template_guid_id_map[child_guid] = curr_size
            templates_data[curr_template_key]["children"].append(f"Template_{curr_size}")

        # Don't combine these 2 for loops, as we want to have consecutive IDs for children
        for child_guid in children_guids:
            self._build_template_data(child_guid, templates_data, templates, template_guid_id_map)
```

</details>

[Back to contents](#contents)

<a id="c03"></a>

## C03. Pad and concatenate plot arrays once

**Behavior-sensitive.** The current loop allocates a new array per missing column and recopies previously concatenated queries.

**Compatibility:** The two-dimensional fast path below retains the original loop for other dimensions and representations. Retain float dtype, NaN padding, labels, the single-array result, and array layout. Concatenating all arrays together can choose a different memory layout from successive concatenations; that remains a compatibility requirement. Leave normalization and min/max operations untouched.

Reference: [NumPy insert](https://numpy.org/doc/stable/reference/generated/numpy.insert.html).

<details>
<summary>utils/report_objects.py:240–271</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L240-L271)  
**Lines:** 240–271

**Current**

```python
    # cleanup and extend arrays...
    rowlbls = list()
    array = None
    yaxis_txt = "["
    xaxis_txt = "["
    i = 0
    for tmp in plot_data:
        # special case: Nexus will use the X axis row name as the title
        # instead of xtitle.  If the name provided by the query aligns
        # with the plotter title, we will use the plotter title instead as
        # it may include things like units...
        tmp_title = tmp["xname"]
        if x_axis_title.startswith(tmp_title):
            tmp_title = x_axis_title
        rowlbls.append(tmp_title)
        rowlbls.append(tmp["yname"])
        if i > 0:
            xaxis_txt += ","
            yaxis_txt += ","
        xaxis_txt += f"{i}"
        yaxis_txt += f"{i + 1}"
        i += 2
        a = tmp["array"]
        # pad out the array to match the largest (making concatenation possible)
        while a.shape[1] < max_columns:
            a = numpy.insert(a, a.shape[1], numpy.nan, 1)
        if array is None:
            array = a
        else:
            array = numpy.concatenate([array, a])
    xaxis_txt += "]"
    yaxis_txt += "]"
```

**Alternative**

```python
    if all(
        type(tmp["array"]) is numpy.ndarray
        and tmp["array"].ndim == 2
        and tmp["array"].dtype == numpy.dtype(numpy.double)
        for tmp in plot_data
    ):
        # cleanup and extend arrays...
        rowlbls = list()
        array = None
        arrays = []
        yaxis_txt = "["
        xaxis_txt = "["
        i = 0
        for tmp in plot_data:
            # special case: Nexus will use the X axis row name as the title
            # instead of xtitle.  If the name provided by the query aligns
            # with the plotter title, we will use the plotter title instead as
            # it may include things like units...
            tmp_title = tmp["xname"]
            if x_axis_title.startswith(tmp_title):
                tmp_title = x_axis_title
            rowlbls.append(tmp_title)
            rowlbls.append(tmp["yname"])
            if i > 0:
                xaxis_txt += ","
                yaxis_txt += ","
            xaxis_txt += f"{i}"
            yaxis_txt += f"{i + 1}"
            i += 2
            a = tmp["array"]
            # pad out the array to match the largest (making concatenation possible)
            if a.shape[1] < max_columns:
                order = "F" if a.flags.f_contiguous else "C"
                padded = numpy.full((a.shape[0], max_columns), numpy.nan, dtype=a.dtype, order=order)
                padded[:, : a.shape[1]] = a
                a = padded
            arrays.append(a)
        if len(arrays) == 1:
            array = arrays[0]
        elif arrays:
            array = numpy.concatenate(arrays, axis=0)
        xaxis_txt += "]"
        yaxis_txt += "]"
    else:
        # cleanup and extend arrays...
        rowlbls = list()
        array = None
        yaxis_txt = "["
        xaxis_txt = "["
        i = 0
        for tmp in plot_data:
            # special case: Nexus will use the X axis row name as the title
            # instead of xtitle.  If the name provided by the query aligns
            # with the plotter title, we will use the plotter title instead as
            # it may include things like units...
            tmp_title = tmp["xname"]
            if x_axis_title.startswith(tmp_title):
                tmp_title = x_axis_title
            rowlbls.append(tmp_title)
            rowlbls.append(tmp["yname"])
            if i > 0:
                xaxis_txt += ","
                yaxis_txt += ","
            xaxis_txt += f"{i}"
            yaxis_txt += f"{i + 1}"
            i += 2
            a = tmp["array"]
            # pad out the array to match the largest (making concatenation possible)
            while a.shape[1] < max_columns:
                a = numpy.insert(a, a.shape[1], numpy.nan, 1)
            if array is None:
                array = a
            else:
                array = numpy.concatenate([array, a])
        xaxis_txt += "]"
        yaxis_txt += "]"
```

</details>

[Back to contents](#contents)

<a id="c04"></a>

## C04. Remove one copy from writable NumPy conversion

**Behavior-sensitive.** The writable branch constructs a full bytes snapshot and then deep-copies its NumPy view.

**Compatibility:** The guarded branch accepts only a literal boolean and the ordinary `array.array` backing store. Other representations, including non-contiguous arrays with a working `tobytes()` method, retain the original conversion. The fallback also preserves when custom truth values are evaluated. The temporary buffer view can still change concurrent-resize failures and the snapshot observed during copying. Keep the bytes snapshot where those behaviors matter; no temporary view may escape.

Reference: [NumPy frombuffer](https://numpy.org/doc/stable/reference/generated/numpy.frombuffer.html).

<details>
<summary>utils/report_utils.py:697–706</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_utils.py#L697-L706)  
**Lines:** 697–706

**Current**

```python
    def to_numpy(self, writeable=False):
        if not has_numpy:
            raise ImportError
        a = numpy.frombuffer(self.array.tobytes(), dtype=self.dtype)
        a.shape = self.shape
        if writeable:
            import copy

            return copy.deepcopy(a)
        return a
```

**Alternative**

```python
    def to_numpy(self, writeable=False):
        if not has_numpy:
            raise ImportError
        if type(writeable) is bool and writeable and type(self.array) is array.array:
            a = numpy.frombuffer(self.array, dtype=self.dtype)
            a.shape = self.shape
            return a.copy(order="K")
        a = numpy.frombuffer(self.array.tobytes(), dtype=self.dtype)
        a.shape = self.shape
        if writeable:
            import copy

            return copy.deepcopy(a)
        return a
```

</details>

[Back to contents](#contents)

<a id="c05"></a>

## C05. Fill VTK pick identifiers in one native call

**Local change.** Every mesh point currently requires a Python-to-VTK SetValue call for the same integer.

**Compatibility:** Retain vtkIntArray, name, tuple/component counts, AddArray and Modified calls. Keep the zero-point case from converting part_id when the old loop would do nothing.

Reference: [VTK FillValue](https://vtk.org/doc/nightly/html/classvtkIntArray.html). VTK is already an optional project dependency.

<details>
<summary>utils/enhanced_images.py:323–332</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/enhanced_images.py#L323-L332)  
**Lines:** 323–332

**Current**

```python
    def _add_pick_data(poly_data: vtk.vtkPolyData, part_id: int):
        arr = vtk.vtkIntArray()
        arr.SetName("Pick Data")
        arr.SetNumberOfComponents(1)
        num_points = poly_data.GetNumberOfPoints()
        arr.SetNumberOfTuples(num_points)
        for i in range(num_points):
            arr.SetValue(i, part_id)
        poly_data.GetPointData().AddArray(arr)
        poly_data.Modified()
```

**Proposed**

```python
    def _add_pick_data(poly_data: vtk.vtkPolyData, part_id: int):
        arr = vtk.vtkIntArray()
        arr.SetName("Pick Data")
        arr.SetNumberOfComponents(1)
        num_points = poly_data.GetNumberOfPoints()
        arr.SetNumberOfTuples(num_points)
        if num_points:
            arr.FillValue(part_id)
        poly_data.GetPointData().AddArray(arr)
        poly_data.Modified()
```

</details>

[Back to contents](#contents)

<a id="s01"></a>

## S01. Use a local membership set when preparing fields for save

**Local change.** Each proxy field currently searches the tuple of ORM field names. A set removes repeated linear membership searches.

**Compatibility:** Only replace the local model_fields value. Keep the public/helper return format, processing order, relation writes, and exception boundaries.

<details>
<summary>serverless/base.py:480–484</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/serverless/base.py#L480-L484)  
**Lines:** 480–484

**Current**

```python
        target_db = kwargs.pop("using", "default")
        cls_fields = self._get_field_names() + self._get_prop_field_names()
        model_fields = self._get_orm_field_names(self._orm_instance)
        for field_ in cls_fields:
            if field_ not in model_fields:
```

**Proposed**

```python
        target_db = kwargs.pop("using", "default")
        cls_fields = self._get_field_names() + self._get_prop_field_names()
        model_fields = set(self._get_orm_field_names(self._orm_instance))
        for field_ in cls_fields:
            if field_ not in model_fields:
```

</details>

[Back to contents](#contents)

<a id="s02"></a>

## S02. Avoid temporary tuples for flat value extraction

**Local change.** The single-field flat case allocates one tuple per object and then allocates the final flattened list.

**Compatibility:** Use the fast path only for `flat is True` with exactly one field. The original path retains zero-field iteration, custom truth-value timing, and tuple results. Preserve the missing-attribute fallback and the generator's `RuntimeError` conversion if a property raises `StopIteration`.

Reference: [Generator exception behavior](https://peps.python.org/pep-0479/).

<details>
<summary>serverless/base.py:935–942</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/serverless/base.py#L935-L942)  
**Lines:** 935–942

**Current**

```python
        if flat and len(fields) > 1:
            raise ValueError(
                "'flat' is not valid when values_list is called with more than one field."
            )
        ret = []
        for obj in self._obj_set:
            ret.append(tuple(getattr(obj, f, None) for f in fields))
        return list(chain.from_iterable(ret)) if flat else ret
```

**Proposed**

```python
        if flat and len(fields) > 1:
            raise ValueError(
                "'flat' is not valid when values_list is called with more than one field."
            )
        if flat is True and len(fields) == 1:
            field = fields[0]
            ret = []
            for obj in self._obj_set:
                try:
                    value = getattr(obj, field, None)
                except StopIteration as exc:
                    raise RuntimeError("generator raised StopIteration") from exc
                ret.append(value)
            return ret
        ret = []
        for obj in self._obj_set:
            ret.append(tuple(getattr(obj, f, None) for f in fields))
        return list(chain.from_iterable(ret)) if flat else ret
```

</details>

[Back to contents](#contents)

<a id="s03"></a>

## S03. Build template JSON into one accumulator

**Behavior-sensitive.** Deep template trees repeatedly copy descendant dictionary entries into every ancestor's return dictionary.

**Compatibility:** The bound-method check preserves class and instance overrides of `_to_dict`; the fallback appends the child's key before merging its result, as today. The new helper still changes recursion depth, partial accumulator updates, and dispatch through `_append_to_dict`. Resolve subclass helper-name collisions and failure behavior before adoption. Keep IDs, dictionary order, fresh root GUIDs, duplicate visitation, and parent references.

<details>
<summary>serverless/template.py:166–204</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/serverless/template.py#L166-L204)  
**Lines:** 166–204

**Current**

```python
    def _to_dict(
        self,
        next_id: int = 0,
        guid_id_map: dict[str, int] | None = None,
    ) -> tuple[dict, dict[str, int], int]:
        """Recursively build a JSON-serializable template tree."""
        if guid_id_map is None:
            guid_id_map = {}

        # Assign an index to this template and build its key.
        guid_id_map[self.guid] = next_id
        curr_key = f"Template_{next_id}"
        next_id += 1

        # Copy selected attributes to the JSON payload.
        curr_data = {
            k: getattr(self, k) for k in JSON_ATTR_KEYS if getattr(self, k, None) is not None
        }

        # Normalized/derived fields.
        curr_data["params"] = self.get_params()
        curr_data["sort_selection"] = self.get_sort_selection()
        # Root templates get a fresh GUID in the JSON representation.
        curr_data["guid"] = str(uuid.uuid4()) if self.parent is None else None
        curr_data["parent"] = (
            None if self.parent is None else f"Template_{guid_id_map[self.parent.guid]}"
        )

        curr_data["children"] = []
        templates_data = {curr_key: curr_data}

        # Recurse over children and build their entries.
        for child in self.children:
            child_dict, guid_id_map, next_id = child._to_dict(next_id, guid_id_map)
            child_key = f"Template_{guid_id_map[child.guid]}"
            curr_data["children"].append(child_key)
            templates_data.update(child_dict)

        return templates_data, guid_id_map, next_id
```

**Alternative**

```python
    def _to_dict(
        self,
        next_id: int = 0,
        guid_id_map: dict[str, int] | None = None,
    ) -> tuple[dict, dict[str, int], int]:
        if guid_id_map is None:
            guid_id_map = {}
        templates_data = {}
        guid_id_map, next_id = self._append_to_dict(templates_data, next_id, guid_id_map)
        return templates_data, guid_id_map, next_id

    def _append_to_dict(
        self, templates_data: dict, next_id: int, guid_id_map: dict[str, int]
    ) -> tuple[dict[str, int], int]:
        # Assign an index to this template and build its key.
        guid_id_map[self.guid] = next_id
        curr_key = f"Template_{next_id}"
        next_id += 1

        # Copy selected attributes to the JSON payload.
        curr_data = {
            k: getattr(self, k) for k in JSON_ATTR_KEYS if getattr(self, k, None) is not None
        }

        # Normalized/derived fields.
        curr_data["params"] = self.get_params()
        curr_data["sort_selection"] = self.get_sort_selection()
        # Root templates get a fresh GUID in the JSON representation.
        curr_data["guid"] = str(uuid.uuid4()) if self.parent is None else None
        curr_data["parent"] = (
            None if self.parent is None else f"Template_{guid_id_map[self.parent.guid]}"
        )
        curr_data["children"] = []
        templates_data[curr_key] = curr_data
        for child in self.children:
            child_method = child._to_dict
            if (
                getattr(child_method, "__func__", None) is Template._to_dict
                and getattr(child_method, "__self__", None) is child
            ):
                guid_id_map, next_id = child._append_to_dict(
                    templates_data, next_id, guid_id_map
                )
                child_key = f"Template_{guid_id_map[child.guid]}"
                curr_data["children"].append(child_key)
            else:
                child_dict, guid_id_map, next_id = child_method(next_id, guid_id_map)
                child_key = f"Template_{guid_id_map[child.guid]}"
                curr_data["children"].append(child_key)
                templates_data.update(child_dict)
        return guid_id_map, next_id
```

</details>

[Back to contents](#contents)

<a id="s04"></a>

## S04. Skip the ineffective byte-cell string check for plain two-dimensional NumPy arrays

**Local change.** A plain NumPy array with dtype.kind == 'S' yields bytes scalars, so the per-cell isinstance(value, str) test never succeeds.

**Compatibility:** Keep the original walk for subclasses, fallback nexus_array objects and non-2D shapes. Retain effective validation, legacy shape errors, and the original object identity.

Reference: [NumPy scalar types](https://numpy.org/doc/1.26/reference/arrays.scalars.html).

<details>
<summary>utils/report_objects.py:1296–1300</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L1296-L1300)  
**Lines:** 1296–1300

**Current**

```python
        if kind == "S":  # Check if the array contains strings
            for i in range(array.shape[0]):
                for j in range(array.shape[1]):
                    if isinstance(array[i, j], str):
                        self.validate_string(array[i, j], "Table array element", sanitize_html=True)
```

**Proposed**

```python
        plain_byte_array = (
            has_numpy and type(array) is numpy.ndarray and array.ndim == 2
        )
        if kind == "S" and not plain_byte_array:
            for i in range(array.shape[0]):
                for j in range(array.shape[1]):
                    if isinstance(array[i, j], str):
                        self.validate_string(array[i, j], "Table array element", sanitize_html=True)
```

</details>

[Back to contents](#contents)

<a id="s05"></a>

## S05. Reuse one sanitizer during a validation traversal

**Behavior-sensitive.** `bleach.clean` constructs sanitizer machinery for each leaf string. A traversal-scoped `Cleaner` can reuse that setup.

**Compatibility:** Keep cleaning defaults, HTML/properties exemptions, field names, exception text, and traversal order. The proposed private traversal helpers bypass replacements of `_check_string_for_html` and the recursive public functions, even though their direct entry points remain available. Preserve those customizations before adoption. Each traversal needs its own cleaner because its parser is not thread-safe.

Reference: [Bleach Cleaner reuse](https://bleach.readthedocs.io/en/latest/clean.html#using-bleach-sanitizer-cleaner).

<details>
<summary>core/common_utils.py:464–516</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/common_utils.py#L464-L516)  
**Lines:** 464–516

**Current**

```python
def _check_string_for_html(value: str, field_name: str) -> None:
    """Helper function to validate that a string does not contain HTML content.

    Args:
        value: String value to validate
        field_name: Name of the field being validated for error messages

    Raises:
        ValueError: If the string contains HTML content
    """
    cleaned_string = bleach.clean(value, strip=True)
    if cleaned_string != value:
        raise ValueError(f"{field_name} contains HTML content. Value: {value}")


def check_dictionary_for_html(data):
    for key, value in data.items():
        # Do not validate HTML key
        if key == "HTML":
            continue

        # Recursive case for nested dictionaries
        if isinstance(value, dict):
            # Specific checks for properties key
            if key == "properties":
                subdict = {k: v for k, v in value.items() if k not in PROPERTIES_EXEMPT}
                check_dictionary_for_html(subdict)
            else:
                check_dictionary_for_html(value)

        # Check for lists
        elif isinstance(value, list):
            check_list_for_html(value, key)

        # Main check for strings
        elif isinstance(value, str):
            _check_string_for_html(value, key)

        # Ignore other types
        else:
            continue


def check_list_for_html(value_list, key):
    for item in value_list:
        if isinstance(item, str):
            _check_string_for_html(item, key)
        elif isinstance(item, dict):
            check_dictionary_for_html(item)
        elif isinstance(item, list):
            check_list_for_html(item, key)
        else:
            continue
```

**Alternative**

```python
def _check_string_for_html(value: str, field_name: str) -> None:
    """Helper function to validate that a string does not contain HTML content.

    Args:
        value: String value to validate
        field_name: Name of the field being validated for error messages

    Raises:
        ValueError: If the string contains HTML content
    """
    cleaned_string = bleach.clean(value, strip=True)
    if cleaned_string != value:
        raise ValueError(f"{field_name} contains HTML content. Value: {value}")

def _make_html_checker():
    cleaner = None

    def check(value: str, field_name: str) -> None:
        nonlocal cleaner
        if cleaner is None:
            cleaner = bleach.Cleaner(strip=True)
        cleaned_string = cleaner.clean(value)
        if cleaned_string != value:
            raise ValueError(f"{field_name} contains HTML content. Value: {value}")

    return check


def check_dictionary_for_html(data):
    _check_dictionary_values(data, _make_html_checker())


def _check_dictionary_values(data, check):
    for key, value in data.items():
        if key == "HTML":
            continue
        if isinstance(value, dict):
            if key == "properties":
                subdict = {k: v for k, v in value.items() if k not in PROPERTIES_EXEMPT}
                _check_dictionary_values(subdict, check)
            else:
                _check_dictionary_values(value, check)
        elif isinstance(value, list):
            _check_list_values(value, key, check)
        elif isinstance(value, str):
            check(value, key)


def check_list_for_html(value_list, key):
    _check_list_values(value_list, key, _make_html_checker())


def _check_list_values(value_list, key, check):
    for item in value_list:
        if isinstance(item, str):
            check(item, key)
        elif isinstance(item, dict):
            _check_dictionary_values(item, check)
        elif isinstance(item, list):
            _check_list_values(item, key, check)
```

</details>

[Back to contents](#contents)

<a id="u01"></a>

## U01. Combine the fixed PDF-width selector queries

**Behavior-sensitive.** The probe creates separate NodeLists for its fixed selectors. A combined query can avoid those temporary collections.

**Compatibility:** The existing `seen` set already measures each element only once. The combined query changes traversal from selector-group order to document order; it does not remove duplicate layout measurements. The maximum is equivalent for stable geometry, but animations or custom measurement hooks can observe the new order. Keep the selectors, report root, readiness, visibility checks, and measurement formula. Query speed depends on the browser.

Reference: [Element.querySelectorAll](https://developer.mozilla.org/en-US/docs/Web/API/Element/querySelectorAll).

<details>
<summary>utils/pdf_renderer.py:774–777</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/pdf_renderer.py#L774-L777)  
**Lines:** 774–777

JavaScript inside the existing page.evaluate string. Keep the existing seen set initially to minimize the edit.

**Current**

```javascript
                    const candidates = [root];
                    for (const selector of candidateSelectors) {
                        candidates.push(...root.querySelectorAll(selector));
                    }
```

**Alternative**

```javascript
                    const candidates = [
                        root,
                        ...root.querySelectorAll(candidateSelectors.join(','))
                    ];
```

</details>

[Back to contents](#contents)

<a id="u02"></a>

## U02. Avoid repeated front insertion in REST copy preparation

**Local change.** Every session/dataset insert shifts all items already in copy_list.

**Compatibility:** Preserve set iteration, lookup and callback order, unsuccessful lookup handling, and the existing reversed session/dataset order before items. This proposal covers the item branch only.

<details>
<summary>utils/report_remote_server.py:694–737</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_remote_server.py#L694-L737)  
**Lines:** 694–737

**Current**

```python
        copy_list = []
        # get the items to copy...
        if obj_type == "item":
            # basic objects
            objs = source.get_objects(objtype=report_objects.ItemREST, query=query)
            for o in objs:
                if categories:
                    o.categories = categories
                copy_list.append(o)
            # now the associated datasets
            dataset_set = set()
            session_set = set()
            for o in copy_list:
                dataset_set.add(o.dataset)
                session_set.add(o.session)
            nobjs = len(dataset_set) + len(session_set)
            n = 0
            if progress:
                text = "Scanning datasets..."
                if progress_qt:
                    text = "Scanning datasets..."
                progress.setLabelText(text)
                progress.setMaximum(nobjs)
                progress.setValue(n)
            for guid in dataset_set:
                obj = source.get_object_from_guid(guid, objtype=report_objects.DatasetREST)
                if obj:
                    copy_list.insert(0, obj)
                n += 1
                if progress:
                    progress.setValue(n)
            # now the associated sessions
            if progress:
                text = "Scanning sessions..."
                if progress_qt:
                    text = "Scanning sessions..."
                progress.setLabelText(text)
            for guid in session_set:
                obj = source.get_object_from_guid(guid, objtype=report_objects.SessionREST)
                if obj:
                    copy_list.insert(0, obj)
                n += 1
                if progress:
                    progress.setValue(n)
```

**Proposed**

```python
        copy_list = []
        datasets = []
        sessions = []
        # get the items to copy...
        if obj_type == "item":
            # basic objects
            objs = source.get_objects(objtype=report_objects.ItemREST, query=query)
            for o in objs:
                if categories:
                    o.categories = categories
                copy_list.append(o)
            # now the associated datasets
            dataset_set = set()
            session_set = set()
            for o in copy_list:
                dataset_set.add(o.dataset)
                session_set.add(o.session)
            nobjs = len(dataset_set) + len(session_set)
            n = 0
            if progress:
                text = "Scanning datasets..."
                if progress_qt:
                    text = "Scanning datasets..."
                progress.setLabelText(text)
                progress.setMaximum(nobjs)
                progress.setValue(n)
            for guid in dataset_set:
                obj = source.get_object_from_guid(guid, objtype=report_objects.DatasetREST)
                if obj:
                    datasets.append(obj)
                n += 1
                if progress:
                    progress.setValue(n)
            # now the associated sessions
            if progress:
                text = "Scanning sessions..."
                if progress_qt:
                    text = "Scanning sessions..."
                progress.setLabelText(text)
            for guid in session_set:
                obj = source.get_object_from_guid(guid, objtype=report_objects.SessionREST)
                if obj:
                    sessions.append(obj)
                n += 1
                if progress:
                    progress.setValue(n)
            copy_list = list(reversed(sessions)) + list(reversed(datasets)) + copy_list
```

</details>

[Back to contents](#contents)

<a id="u03"></a>

## U03. Filter REST tags in one pass

**Local change.** BaseRESTObject.rem_tag iterates a copy while each list.remove searches and shifts the original list.

**Compatibility:** Keep shlex parsing, token order, all matching duplicates, and rebuild_tags. Do not transplant this into serverless.rem_tag: mutation during its iteration skips some adjacent matches, which is existing behavior.

<details>
<summary>utils/report_objects.py:650–658</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L650-L658)  
**Lines:** 650–658

**Current**

```python
    def rem_tag(self, tag):
        tags = shlex.split(self.get_tags())
        for t in list(tags):
            if "=" in t:
                if t.split("=")[0] == tag:
                    tags.remove(t)
            elif t == tag:
                tags.remove(t)
        self.rebuild_tags(tags)
```

**Proposed**

```python
    def rem_tag(self, tag):
        tags = shlex.split(self.get_tags())
        remaining = []
        for token in tags:
            if "=" in token:
                if token.split("=")[0] == tag:
                    continue
            elif token == tag:
                continue
            remaining.append(token)
        self.rebuild_tags(remaining)
```

</details>

[Back to contents](#contents)

<a id="u04"></a>

## U04. Join legacy child-order strings once

**Local change.** Both legacy template representations repeatedly concatenate onto self.children_order.

**Compatibility:** Retain trailing commas and the empty-list result. The fast path is restricted to the exact built-in template class, an ordinary list, and plain string GUIDs. Subclasses and unusual GUID values retain the original assignments and conversions, including partial updates. Serverless already joins its child GUIDs.

<details>
<summary>utils/report_objects.py:513–515</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L513-L515)  
**Lines:** 513–515

**Current**

```python
        self.children_order = ""
        for guid in self.children:
            self.children_order += str(guid) + ","
```

**Proposed**

```python
        self.children_order = ""
        if (
            type(self) is Template
            and type(self.children) is list
            and all(type(guid) is str for guid in self.children)
        ):
            self.children_order = "".join(guid + "," for guid in self.children)
        else:
            for guid in self.children:
                self.children_order += str(guid) + ","
```

</details>

<details>
<summary>utils/report_objects.py:1515–1517</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L1515-L1517)  
**Lines:** 1515–1517

**Current**

```python
        self.children_order = ""
        for guid in self.children:
            self.children_order += str(guid) + ","
```

**Proposed**

```python
        self.children_order = ""
        if (
            type(self) is TemplateREST
            and type(self.children) is list
            and all(type(guid) is str for guid in self.children)
        ):
            self.children_order = "".join(guid + "," for guid in self.children)
        else:
            for guid in self.children:
                self.children_order += str(guid) + ","
```

</details>

[Back to contents](#contents)

<a id="u05"></a>

## U05. Split each filter stanza once

**Local change.** The validation loop splits a stanza up to three times.

**Compatibility:** Keep the exact validation sequence and boolean return values. Make this change in the generation input for adr_utils.py.

<details>
<summary>codegen/adr_utils.txt:181–189</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/codegen/adr_utils.txt#L181-L189)  
**Lines:** 181–189

**Current**

```python
    for query_stanza in item_filter.split(";"):
        if len(query_stanza) > 0:
            if len(query_stanza.split("|")) != 4:
                return False
            if query_stanza.split("|")[0] not in ["A", "O"]:
                return False
            if query_stanza.split("|")[1][0:2] not in ["i_", "s_", "d_", "t_"]:
                return False
    return True
```

**Proposed**

```python
    for query_stanza in item_filter.split(";"):
        if len(query_stanza) > 0:
            parts = query_stanza.split("|")
            if len(parts) != 4:
                return False
            if parts[0] not in ["A", "O"]:
                return False
            if parts[1][0:2] not in ["i_", "s_", "d_", "t_"]:
                return False
    return True
```

</details>

[Back to contents](#contents)

<a id="u06"></a>

## U06. Stop splitting tags after the fields that are used

**Small saving.** Tag rebuilding uses only the first two components of `split("=")`; removal uses only the first. Tokens containing many equals signs allocate unused components.

**Compatibility:** For rebuilding, use a maximum of two splits, not one: the existing code turns `a=b=c` into `a=b`, discarding later components. Removal needs only one split. Preserve serverless removal's in-place iteration and its skipped adjacent matches. Direct rebuild callers with custom string objects retain the original call signature. The REST removal span overlaps U03.

<details>
<summary>serverless/base.py:373</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/serverless/base.py#L373)  
**Lines:** 373

**Current**

```python
            tag_and_value = tag.split("=")
```

**Proposed**

```python
            tag_and_value = tag.split("=", 2) if type(tag) is str else tag.split("=")
```

</details>

<details>
<summary>utils/report_objects.py:634</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L634)  
**Lines:** 634

**Current**

```python
            a = t.split("=")
```

**Proposed**

```python
            a = t.split("=", 2) if type(t) is str else t.split("=")
```

</details>

<details>
<summary>serverless/base.py:826</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/serverless/base.py#L826)  
**Lines:** 826

**Current**

```python
            if t == tag or t.split("=")[0] == tag:
```

**Proposed**

```python
            if t == tag or t.split("=", 1)[0] == tag:
```

</details>

<details>
<summary>utils/report_objects.py:654</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L654)  
**Lines:** 654

**Current**

```python
                if t.split("=")[0] == tag:
```

**Proposed**

```python
                if t.split("=", 1)[0] == tag:
```

</details>

[Back to contents](#contents)

<a id="u07"></a>

## U07. Reuse ZIP metadata while locating thumbnails

**Local change.** `namelist()` builds a filename list from metadata the archive already holds. Iterating `infolist()` avoids that extra list; the AVZ search can also stop before walking every metadata entry.

**Compatibility:** Keep archive order, case handling, warnings, and existing reads/writes. Keep `archive.open(name)`, rather than opening the `ZipInfo` object: duplicate names must retain the existing name-based lookup. The SCDOC branch still writes every matching thumbnail; only AVZ stops at the first match. Opening the ZIP still reads its directory.

References: [ZipFile.infolist](https://docs.python.org/3.10/library/zipfile.html#zipfile.ZipFile.infolist) and [CPython ZIP implementation](https://github.com/python/cpython/blob/3.10/Lib/zipfile.py).

<details>
<summary>utils/geofile_processing.py:117–126</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/geofile_processing.py#L117-L126)  
**Lines:** 117–126

**Current**

```python
        with zipfile.ZipFile(avz_filename) as archive:
            for name in archive.namelist():
                if name.endswith("thumbnail.png"):
                    with archive.open(name) as proxy_file:
                        data = proxy_file.read()
                        try:
                            with open(os.path.join(avz_dir, "proxy.png"), "wb") as output_file:
                                output_file.write(data)
                        except OSError as e:
                            print(f"Warning: unable to extract SCDOC proxy image: {str(e)}")
```

**Proposed**

```python
        with zipfile.ZipFile(avz_filename) as archive:
            for entry in archive.infolist():
                name = entry.filename
                if name.endswith("thumbnail.png"):
                    with archive.open(name) as proxy_file:
                        data = proxy_file.read()
                        try:
                            with open(os.path.join(avz_dir, "proxy.png"), "wb") as output_file:
                                output_file.write(data)
                        except OSError as e:
                            print(f"Warning: unable to extract SCDOC proxy image: {str(e)}")
```

</details>

<details>
<summary>utils/geofile_processing.py:161–168</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/geofile_processing.py#L161-L168)  
**Lines:** 161–168

**Current**

```python
        with zipfile.ZipFile(avz_filename) as archive:
            for name in archive.namelist():
                if name.lower().endswith("proxy.png"):
                    with archive.open(name) as proxy_file:
                        data = proxy_file.read()
                        with open(os.path.join(avz_dir, "proxy.png"), "wb") as output_file:
                            output_file.write(data)
                    break
```

**Proposed**

```python
        with zipfile.ZipFile(avz_filename) as archive:
            for entry in archive.infolist():
                name = entry.filename
                if name.lower().endswith("proxy.png"):
                    with archive.open(name) as proxy_file:
                        data = proxy_file.read()
                        with open(os.path.join(avz_dir, "proxy.png"), "wb") as output_file:
                            output_file.write(data)
                    break
```

</details>

[Back to contents](#contents)

<a id="d01"></a>

## D01. Eagerly load item session and dataset relations

**Behavior-sensitive.** The client converts each ORM item and then touches both foreign keys. The installed v261 ItemManager does not preload them. One joined queryset can avoid two additional reads per ordinary item.

**Compatibility:** These snippets target data.models.Item only. Verify database routing, concurrent updates, missing/corrupt relations, custom subclasses, and all supported installation versions. Keep ObjectSet eager and retain its proxy conversion. QuerySet is already imported in this module.

Reference: [Django select_related](https://docs.djangoproject.com/en/4.2/ref/models/querysets/#select-related). These SQL changes are deferred under the strict compatibility requirement.

<details>
<summary>serverless/base.py:715–717</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/serverless/base.py#L715-L717)  
**Lines:** 715–717

**Current**

```python
            orm_instance = cls._orm_model_cls.objects.using(kwargs.pop("using", "default")).get(
                **kwargs
            )
```

**Alternative**

```python
            qs = cls._orm_model_cls.objects.using(kwargs.pop("using", "default"))
            if cls._orm_model == "data.models.Item":
                qs = qs.select_related("session", "dataset")
            orm_instance = qs.get(**kwargs)
```

</details>

<details>
<summary>serverless/base.py:748–749</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/serverless/base.py#L748-L749)  
**Lines:** 748–749

**Current**

```python
        qs = cls._orm_model_cls.objects.using(db_alias).filter(**filter_kwargs)
        return ObjectSet(_model=cls, _orm_model=cls._orm_model_cls, _orm_queryset=qs)
```

**Alternative**

```python
        qs = cls._orm_model_cls.objects.using(db_alias).filter(**filter_kwargs)
        if cls._orm_model == "data.models.Item":
            qs = qs.select_related("session", "dataset")
        return ObjectSet(_model=cls, _orm_model=cls._orm_model_cls, _orm_queryset=qs)
```

</details>

<details>
<summary>serverless/base.py:767–768</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/serverless/base.py#L767-L768)  
**Lines:** 767–768

**Current**

```python
        qs = cls._orm_model_cls.find(query=query)
        return ObjectSet(_model=cls, _orm_model=cls._orm_model_cls, _orm_queryset=qs)
```

**Alternative**

```python
        qs = cls._orm_model_cls.find(query=query)
        if cls._orm_model == "data.models.Item" and isinstance(qs, QuerySet):
            qs = qs.select_related("session", "dataset")
        return ObjectSet(_model=cls, _orm_model=cls._orm_model_cls, _orm_queryset=qs)
```

</details>

[Back to contents](#contents)

<a id="d02"></a>

## D02. Query report names without hydrating complete template trees

**Behavior-sensitive.** get_reports(fields=['name'], flat=True) first hydrates each root and its descendants, then extracts names.

**Compatibility:** The approach bypasses hydration errors, subclass dispatch, property access, and malformed-tree detection. Those are observable differences. Keep the existing implementation until those semantics are explicitly resolved; do not generalize arbitrary proxy fields to ORM values_list.

<details>
<summary>serverless/adr.py:1361–1364</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/serverless/adr.py#L1361-L1364)  
**Lines:** 1361–1364

This approach changes behavior for some existing inputs.

**Current**

```python
        out = Template.filter(parent=None)
        if fields:
            out = out.values_list(*fields, flat=flat)
        return out
```

**Alternative**

```python
        if fields == ["name"] and flat:
            return list(
                Template._orm_model_cls.objects.filter(parent=None).values_list("name", flat=True)
            )
        out = Template.filter(parent=None)
        if fields:
            out = out.values_list(*fields, flat=flat)
        return out
```

</details>

[Back to contents](#contents)

<a id="d03"></a>

## D03. Deep-copy a template graph once before walking it

**Behavior-sensitive.** _copy_template deep-copies the remaining subtree at every recursive call; parent links can bring additional graph data into those copies.

**Compatibility:** The approach preserves parent database lookups and save order, but it changes how aliases between mutable values in different nodes survive and how often __deepcopy__ hooks run. Resolve those differences before adopting it. Never replace the deep copy with an unconditional shallow copy.

<details>
<summary>serverless/adr.py:2103–2133</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/serverless/adr.py#L2103-L2133)  
**Lines:** 2103–2133

**Current**

```python
    def _copy_template(self, template: Template, **kwargs) -> Template:
        """Internal helper to deep-copy a template subtree into another DB.

        This performs a depth-first copy of ``template`` and all its
        descendants, preserving GUIDs and child ordering.
        """
        # Depth-first walk down from the root and copy children along the way.
        out_template = copy.deepcopy(template)
        if out_template.parent is not None:
            parent = out_template.parent
            # Parents are always copied first, so they should exist in the target.
            out_template.parent = Template.get(
                guid=parent.guid,
                using=kwargs.get("using", "default"),
            )
        # Preserve legacy ordering semantics.
        out_template.reorder_children()
        children = out_template.children
        out_template.children = []
        out_template.reinit()
        out_template.save(**kwargs)

        new_children: list[Template] = []
        for child in children:
            child.parent = out_template
            new_child = self._copy_template(child, **kwargs)
            new_children.append(new_child)
        out_template.children = new_children
        out_template.update_children_order()
        out_template.save(**kwargs)
        return out_template
```

**Alternative**

```python
    def _copy_template(self, template: Template, **kwargs) -> Template:
        """Internal helper to deep-copy a template subtree into another DB.

        This performs a depth-first copy of ``template`` and all its
        descendants, preserving GUIDs and child ordering.
        """
        # Depth-first walk down from the root and copy children along the way.
        return self._copy_template_node(copy.deepcopy(template), **kwargs)

    def _copy_template_node(self, out_template: Template, **kwargs) -> Template:
        if out_template.parent is not None:
            parent = out_template.parent
            # Parents are always copied first, so they should exist in the target.
            out_template.parent = Template.get(
                guid=parent.guid,
                using=kwargs.get("using", "default"),
            )
        # Preserve legacy ordering semantics.
        out_template.reorder_children()
        children = out_template.children
        out_template.children = []
        out_template.reinit()
        out_template.save(**kwargs)

        new_children: list[Template] = []
        for child in children:
            child.parent = out_template
            new_child = self._copy_template_node(child, **kwargs)
            new_children.append(new_child)
        out_template.children = new_children
        out_template.update_children_order()
        out_template.save(**kwargs)
        return out_template
```

</details>

[Back to contents](#contents)

<a id="d04"></a>

## D04. Reuse target relation lookups while copying items

**Behavior-sensitive.** Items sharing a session or dataset repeat target-database lookups during one copy operation.

**Compatibility:** Initialize session_cache = {} and dataset_cache = {} immediately before the item loop. This approach shares proxies across items and returns an earlier database snapshot. That changes existing object identity and concurrent-update behavior. Do not apply it under strict equivalence without resolving those contracts.

<details>
<summary>serverless/adr.py:2220–2227</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/serverless/adr.py#L2220-L2227)  
**Lines:** 2220–2227

**Current**

```python
                try:
                    session = Session.get(guid=item.session.guid, using=target_database)
                except Session.DoesNotExist:
                    session = Session.create(**item.session.as_dict(), using=target_database)
                try:
                    dataset = Dataset.get(guid=item.dataset.guid, using=target_database)
                except Dataset.DoesNotExist:
                    dataset = Dataset.create(**item.dataset.as_dict(), using=target_database)
```

**Alternative**

```python
                session_key = (target_database, Session, item.session.guid)
                session = session_cache.get(session_key)
                if session is None:
                    try:
                        session = Session.get(guid=item.session.guid, using=target_database)
                    except Session.DoesNotExist:
                        session = Session.create(**item.session.as_dict(), using=target_database)
                    session_cache[session_key] = session
                dataset_key = (target_database, Dataset, item.dataset.guid)
                dataset = dataset_cache.get(dataset_key)
                if dataset is None:
                    try:
                        dataset = Dataset.get(guid=item.dataset.guid, using=target_database)
                    except Dataset.DoesNotExist:
                        dataset = Dataset.create(**item.dataset.as_dict(), using=target_database)
                    dataset_cache[dataset_key] = dataset
```

</details>

[Back to contents](#contents)

<a id="d05"></a>

## D05. Avoid refetching every template for each listed report

**Behavior-sensitive.** get_list_reports('report') fetches all templates once and then each Report constructor repeats that complete request.

**Compatibility:** Report already accepts report_obj. The guarded approach preserves the legacy path when root names are duplicated. Even for unique names it uses one snapshot and removes later request failures, so it remains conditional.

The existing constructor fast path is in adr_report.py:77-83; its name lookup chooses the first matching root at adr_report.py:103-108.

<details>
<summary>core/adr_service.py:997–999</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/adr_service.py#L997-L999)  
**Lines:** 997–999

**Current**

```python
                reports = [x for x in all_reports if x.parent is None]
                for i in reports:
                    r_list.append(Report(service=self, report_name=i.name))
```

**Alternative**

```python
                reports = [x for x in all_reports if x.parent is None]
                names = [report.name for report in reports]
                if len(names) == len(set(names)):
                    for report in reports:
                        r_list.append(
                            Report(service=self, report_name=report.name, report_obj=report)
                        )
                else:
                    for report in reports:
                        r_list.append(Report(service=self, report_name=report.name))
```

</details>

[Back to contents](#contents)

<a id="d06"></a>

## D06. Reuse local asset reads and successful writes within an export

**Behavior-sensitive.** The favicon is read twice for two targets. Viewer assets can also pass through special copying and ordinary HTML reference copying separately.

**Compatibility:** The narrow favicon approach still changes what happens if the source changes or the second read would fail. General caching must include source, destination, rewrite mode, export lifetime, and invalidation when another source overwrites the same destination. The fast path also bypasses an overridden `_copy_static_file`; it needs the original calls for that customization. Keep warnings and overwrite order. Do not skip files based only on basename or existence.

<details>
<summary>serverless/html_exporter.py:345–346</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/serverless/html_exporter.py#L345-L346)  
**Lines:** 345–346

Create the first destination directory before reading, and retain the rewrite hook for both destinations. The second source check/read is still removed, so the original two calls remain required where their failures or file changes are observable.

**Current**

```python
        self._copy_static_file("website/images/favicon.png", "media/favicon.png")
        self._copy_static_file("website/images/favicon.png", "media/favicon.ico")
```

**Alternative**

```python
        source_file = self._static_dir / "website/images/favicon.png"
        if source_file.is_file():
            first_target = self._output_dir / "media/favicon.png"
            first_target.parent.mkdir(parents=True, exist_ok=True)
            content = source_file.read_bytes()
            first_target.write_bytes(
                self._fix_viewer_component_paths(str(first_target), content)
            )
            second_target = self._output_dir / "media/favicon.ico"
            second_target.parent.mkdir(parents=True, exist_ok=True)
            second_target.write_bytes(
                self._fix_viewer_component_paths(str(second_target), content)
            )
        else:
            self._copy_static_file("website/images/favicon.png", "media/favicon.png")
            self._copy_static_file("website/images/favicon.png", "media/favicon.ico")
```

</details>

<details>
<summary>serverless/html_exporter.py:404–427</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/serverless/html_exporter.py#L404-L427)  
**Lines:** 404–427

Retain this code: source/destination caching needs explicit invalidation and matching failure behavior.

**Current**

```python
    def _copy_static_file(self, source_rel_path: str, target_rel_path: str, silent: bool = False):
        """Helper to copy a single file from the static source to the output directory.

        Parameters
        ----------
        source_rel_path : str
            Path relative to the static root.
        target_rel_path : str
            Path relative to the output directory.
        silent : bool, optional
            When True, missing source files are silently skipped instead of
            emitting a warning.  Use this for optional/backward-compat assets
            (e.g. MathJax 2.x files that may not exist on newer ADR installs).
        """
        source_file = self._static_dir / source_rel_path
        target_file = self._output_dir / target_rel_path
        if source_file.is_file():
            target_file.parent.mkdir(parents=True, exist_ok=True)
            content = source_file.read_bytes()
            # Patch some viewer JS internals (loader/paths) if needed
            content = self._fix_viewer_component_paths(str(target_file), content)
            target_file.write_bytes(content)
        elif not silent:
            self._logger.warning(f"Warning: Static source file not found: {source_file}")
```

**Keep the current code** to preserve the compatibility requirements above.

</details>

[Back to contents](#contents)

<a id="d07"></a>

## D07. Pool HTTP connections during one remote HTML export

**Behavior-sensitive.** Top-level requests.get/head calls create separate sessions, so consecutive assets do not share one export-scoped connection pool.

**Compatibility:** A Session also persists cookies. Preserve per-call cookie isolation while retaining cookies within redirect chains, proxies, environment-derived authentication, redirects, timeouts, and response cleanup. Unread error responses and interrupted streams also need explicit ownership before a connection can return to the pool. Closing a session is not a substitute for closing those responses. Keep the existing calls until cookie isolation, response cleanup, direct helper calls, and export lifetime are handled together. The Server session has separate authentication and retry configuration.

Reference: [Requests sessions](https://requests.readthedocs.io/en/latest/user/advanced/#session-objects).

<details>
<summary>utils/report_download_html.py:360</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_download_html.py#L360)  
**Lines:** 360

Preserve the existing response handling and request arguments.

**Current**

```python
            resp = requests.get(url, allow_redirects=True, stream=True, timeout=300)
```

**Keep the current call** until the session and response lifetime requirements above are resolved.

</details>

<details>
<summary>utils/report_download_html.py:622</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_download_html.py#L622)  
**Lines:** 622

Keep HEAD redirects disabled.

**Current**

```python
                resp = requests.head(base + sentinel, allow_redirects=False, timeout=300)
```

**Keep the current call** until the session and response lifetime requirements above are resolved.

</details>

<details>
<summary>utils/report_download_html.py:395</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_download_html.py#L395)  
**Lines:** 395

This streaming request needs the same response ownership as the other asset paths.

**Current**

```python
            resp = requests.get(url, allow_redirects=True, stream=True, timeout=300)
```

**Keep the current call** until the session and response lifetime requirements above are resolved.

</details>

<details>
<summary>utils/report_download_html.py:440</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_download_html.py#L440)  
**Lines:** 440

This streaming request needs the same response ownership as the other asset paths.

**Current**

```python
        resp = requests.get(url, allow_redirects=True, stream=True, timeout=300)
```

**Keep the current call** until the session and response lifetime requirements above are resolved.

</details>

<details>
<summary>utils/report_download_html.py:752</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_download_html.py#L752)  
**Lines:** 752

The initial document request is part of the same export.

**Current**

```python
        resp = requests.get(self._url, timeout=300)
```

**Keep the current call** until the session and response lifetime requirements above are resolved.

</details>

[Back to contents](#contents)

<a id="d08"></a>

## D08. Inspect image metadata without first reading the complete file

**Behavior-sensitive.** ImageContent.process reads the full file into bytes solely to open it with Pillow and inspect metadata. Image.save reads it again.

**Compatibility:** Header inspection changes I/O and error behavior for truncated files, enhanced TIFF frames, source changes and file positioning. The saving path still needs full bytes when preserving the original file. Do not cache image contents across validation and save.

<details>
<summary>serverless/item.py:311–325</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/serverless/item.py#L311-L325)  
**Lines:** 311–325

This approach changes file lifetime and failure behavior.

**Current**

```python
    def process(self, value, obj):
        """Validate an image file and record its metadata."""
        file_str = super().process(value, obj)
        with obj._file.open(mode="rb") as f:
            img_bytes = f.read()
        image = PILImage.open(io.BytesIO(img_bytes))
        if obj._file_ext in self.ENHANCED_EXT:
            metadata = is_enhanced(image)
            if not metadata:
                raise ADRException("The enhanced image is empty")
            obj._enhanced = True
        obj._width, obj._height = image.size
        with suppress(OSError):
            image.close()
        return file_str
```

**Alternative**

```python
    def process(self, value, obj):
        file_str = super().process(value, obj)
        with obj._file.open(mode="rb") as f:
            image = PILImage.open(f)
            if obj._file_ext in self.ENHANCED_EXT:
                metadata = is_enhanced(image)
                if not metadata:
                    raise ADRException("The enhanced image is empty")
                obj._enhanced = True
            obj._width, obj._height = image.size
            with suppress(OSError):
                image.close()
        return file_str
```

</details>

<details>
<summary>serverless/item.py:899–917</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/serverless/item.py#L899-L917)  
**Lines:** 899–917

Retain the current save code until the validation/source-lifetime contract is settled.

**Current**

```python
        with self._file.open(mode="rb") as f:
            img_bytes = f.read()
        image = PILImage.open(io.BytesIO(img_bytes))
        # Determine final file name and format
        target_ext = "png" if not self._enhanced else self._file_ext
        self._orm_instance.payloadfile = f"{self.guid}_image.{target_ext}"
        # Save the image
        if self._file_ext != target_ext and target_ext == "png":
            # Convert to PNG format
            self._file_ext = target_ext
            try:
                image.save(self.file_path, format=self._file_ext.upper())
            except OSError as e:
                raise ADRException(f"Error converting image to {self._file_ext}: {e}") from e
        else:  # save image as is (if enhanced or already PNG)
            self._save_file(self.file_path, img_bytes)
        with suppress(OSError):
            image.close()
        super().save(**kwargs)
```

**Keep the current code** to preserve the compatibility requirements above.

</details>

[Back to contents](#contents)

<a id="d09"></a>

## D09. Avoid discovering the same report twice

**Behavior-sensitive.** `Service.get_report` constructs a `Report`, whose constructor already searches the complete template list, then calls the same finder again. Using the constructor's result avoids the second request and scan.

**Compatibility:** The second request can observe report creation, deletion, replacement, or a new error after the first request. Removing it changes those outcomes and the calls made to customized finders. Keep both calls under strict compatibility. The alternative below uses the existing constructor result; it does not add a cache.

The constructor performs the first lookup at [adr_report.py:77–83](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/adr_report.py#L77-L83); the finder assigns `report` on success at [lines 103–108](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/adr_report.py#L103-L108).

<details>
<summary>adr_service.py:941–950</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/adr_service.py#L941-L950)  
**Lines:** 941–950

**Current**

```python
        if self.serverobj is None:
            self.logger.error("Error: no connection to any service")
            raise ConnectionToServiceError
        my_report = Report(service=self, report_name=report_name)
        success = my_report.__find_report_obj__()
        if success:
            return my_report
        else:
            self.logger.error("Error: there is no report with the name {report_name}.")
            raise MissingReportError
```

**Alternative**

```python
        if self.serverobj is None:
            self.logger.error("Error: no connection to any service")
            raise ConnectionToServiceError
        my_report = Report(service=self, report_name=report_name)
        success = getattr(my_report, "report", None) is not None
        if success:
            return my_report
        else:
            self.logger.error("Error: there is no report with the name {report_name}.")
            raise MissingReportError
```

</details>

[Back to contents](#contents)

<a id="m01"></a>

## M01. Avoid copying leading-whitespace HTML solely for document detection

**Small saving.** _wrap_full_document calls lstrip on the complete input before checking only its first 2,000 characters.

**Compatibility:** Preserve Unicode whitespace handling and the same 2,000-character window after leading whitespace. Keep returning the original object when it is already a full document. Retain the original path for string subclasses with custom `lstrip` or slicing behavior. The standard-library `re` module is already imported.

<details>
<summary>serverless/html_exporter.py:157–164</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/serverless/html_exporter.py#L157-L164)  
**Lines:** 157–164

**Current**

```python
        text = html_fragment_or_doc.lstrip()

        # Already a full document? Return as-is.
        # only look at the first ~2KB to avoid scanning huge strings.
        lowered = text[:2000].lower()
        if lowered.startswith("<!doctype") or "<html" in lowered:
            return html_fragment_or_doc
```

**Proposed**

```python
        if type(html_fragment_or_doc) is str:
            first_content = re.search(r"\S", html_fragment_or_doc)
            start = first_content.start() if first_content is not None else len(html_fragment_or_doc)
            lowered = html_fragment_or_doc[start : start + 2000].lower()
            if lowered.startswith("<!doctype") or "<html" in lowered:
                return html_fragment_or_doc
            text = html_fragment_or_doc[start:]
        else:
            text = html_fragment_or_doc.lstrip()
    
            # Already a full document? Return as-is.
            # only look at the first ~2KB to avoid scanning huge strings.
            lowered = text[:2000].lower()
            if lowered.startswith("<!doctype") or "<html" in lowered:
                return html_fragment_or_doc
```

</details>

[Back to contents](#contents)

<a id="m02"></a>

## M02. Determine the REST object factory form once

**Small saving.** get_objects repeats inspect.ismethod(objtype) for every decoded row, although objtype does not change during the call.

**Compatibility:** Retain the valid_database check, constructor choice, exception handling, and response order. This is a small CPU saving relative to the network request.

<details>
<summary>utils/report_remote_server.py:436–470</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_remote_server.py#L436-L470)  
**Lines:** 436–470

**Current**

```python
    def get_objects(self, objtype=report_objects.Template, query=None):
        if not self.valid_database():
            return []
        if inspect.ismethod(objtype):
            obj_uri = getattr(
                inspect.getmodule(objtype),
                objtype.__qualname__.split(".<locals>", 1)[0].rsplit(".", 1)[0],
            ).get_list_url()
        else:
            obj_uri = objtype.get_list_url()
        uri = self.build_request_url(obj_uri)
        # treat None and "" as having no query specified
        if query:
            # translate raw queries into URL savvy text
            tmp = query.strip("\"'").replace("|", "%7C").replace(";", "%3B").replace("#", "%23")
            uri = self.add_query_to_url(uri, f"query={tmp}")

        auth = self.get_auth()
        r = self._http_session.get(uri, auth=auth)
        if r.status_code != requests.codes.ok:
            return []
        try:
            ret = []
            for d in r.json():
                if inspect.ismethod(objtype):
                    t = objtype(d)
                else:
                    t = objtype()
                t.server_api_version = self.api_version
                t.from_json(d)
                ret.append(t)
            return ret
        except Exception as e:
            logger.debug(f"Warning: {str(e)}")
            return []
```

**Proposed**

```python
    def get_objects(self, objtype=report_objects.Template, query=None):
        if not self.valid_database():
            return []
        is_method = inspect.ismethod(objtype)
        if is_method:
            obj_uri = getattr(
                inspect.getmodule(objtype),
                objtype.__qualname__.split(".<locals>", 1)[0].rsplit(".", 1)[0],
            ).get_list_url()
        else:
            obj_uri = objtype.get_list_url()
        uri = self.build_request_url(obj_uri)
        # treat None and "" as having no query specified
        if query:
            # translate raw queries into URL savvy text
            tmp = query.strip("\"'").replace("|", "%7C").replace(";", "%3B").replace("#", "%23")
            uri = self.add_query_to_url(uri, f"query={tmp}")

        auth = self.get_auth()
        r = self._http_session.get(uri, auth=auth)
        if r.status_code != requests.codes.ok:
            return []
        try:
            ret = []
            for d in r.json():
                if is_method:
                    t = objtype(d)
                else:
                    t = objtype()
                t.server_api_version = self.api_version
                t.from_json(d)
                ret.append(t)
            return ret
        except Exception as e:
            logger.debug(f"Warning: {str(e)}")
            return []
```

</details>

[Back to contents](#contents)

<a id="m03"></a>

## M03. Convert ordinary numeric nexus_array rows in bulk

**Behavior-sensitive.** to_2dlist computes an index and constructs an indexing tuple for every cell.

**Compatibility:** Restrict the fast path to exact built-in representations with consistent two-dimensional metadata. Preserve byte-string padding, subclasses, custom accessors, and malformed-shape behavior via the old path. The instance dictionary checks also retain instance-level accessor replacements. Concurrent mutations of shape or backing data remain a compatibility difference. Added guards may outweigh the saving on small arrays.

<details>
<summary>utils/report_utils.py:689–695</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_utils.py#L689-L695)  
**Lines:** 689–695

**Current**

```python
    def to_2dlist(self):
        to_list = list()
        for i in range(self.shape[0]):
            to_list.append(list())
            for j in range(self.shape[1]):
                to_list[i].append(self.__getitem__((i, j)))
        return to_list
```

**Alternative**

```python
    def to_2dlist(self):
        if (
            type(self) is nexus_array
            and "__getitem__" not in self.__dict__
            and "_index" not in self.__dict__
            and type(self.shape) is tuple
            and len(self.shape) == 2
            and all(type(size) is int and size >= 0 for size in self.shape)
            and type(self.dtype) is str
            and self.dtype
            and self.dtype[0] != "S"
            and type(self.array) is array.array
            and len(self.array) == self.shape[0] * self.shape[1]
        ):
            rows, columns = self.shape
            return [
                self.array[row * columns : (row + 1) * columns].tolist()
                for row in range(rows)
            ]
        to_list = list()
        for i in range(self.shape[0]):
            to_list.append(list())
            for j in range(self.shape[1]):
                to_list[i].append(self.__getitem__((i, j)))
        return to_list
```

</details>

[Back to contents](#contents)

<a id="m04"></a>

## M04. Reuse fixed dtype lookup tables

**Small saving.** Two conversion helpers allocate the same small mapping on each call.

**Compatibility:** Place the private mapping constants after imports; preserve every existing key and value, including historical platform-related mappings. This does not justify changing supported dtypes.

Add these module-level constants:

```python
_NUMPY_TO_ARRAY_TYPE = {
    "f4": "f",
    "f8": "d",
    "B": "B",
    "i2": "i",
    "u2": "I",
    "i4": "l",
    "u4": "L",
    "i8": "q",
    "u8": "Q",
}

_NUMPY_TO_NEXUS_TYPE = {
    "f4": "f4",
    "f8": "f8",
    "B": "B",
    "i2": "i2",
    "u2": "u2",
    "i4": "i4",
    "u4": "u4",
    "i8": "i8",
    "u8": "u8",
}
```

<details>
<summary>utils/report_utils.py:627–637</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_utils.py#L627-L637)  
**Lines:** 627–637

**Current**

```python
        np_array_lookup = {
            "f4": "f",
            "f8": "d",
            "B": "B",
            "i2": "i",
            "u2": "I",
            "i4": "l",
            "u4": "L",
            "i8": "q",
            "u8": "Q",
        }
```

**Proposed**

```python
        np_array_lookup = _NUMPY_TO_ARRAY_TYPE
```

</details>

<details>
<summary>utils/report_utils.py:665–675</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_utils.py#L665-L675)  
**Lines:** 665–675

**Current**

```python
        np_array_lookup = {
            "f4": "f4",
            "f8": "f8",
            "B": "B",
            "i2": "i2",
            "u2": "u2",
            "i4": "i4",
            "u4": "u4",
            "i8": "i8",
            "u8": "u8",
        }
```

**Proposed**

```python
        np_array_lookup = _NUMPY_TO_NEXUS_TYPE
```

</details>

[Back to contents](#contents)

<a id="m05"></a>

## M05. Use set membership for a stable integer port-avoidance list

**Behavior-sensitive.** The port scan repeatedly searches avoid, which is commonly a list.

**Compatibility:** A set changes the view of an avoid list mutated during scanning. The guarded approach preserves nonstandard inputs through the old path, but concurrent mutation remains a behavioral difference. Do not change port order, probing, socket handling, or privileged-port behavior.

<details>
<summary>utils/report_utils.py:813–815</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_utils.py#L813-L815)  
**Lines:** 813–815

**Current**

```python
    if avoid is None:
        avoid = []
    ports = list()
```

**Alternative**

```python
    if avoid is None:
        avoid = []
    avoid_lookup = (
        set(avoid)
        if type(avoid) is list and all(type(port) is int for port in avoid)
        else avoid
    )
    ports = list()
```

</details>

<details>
<summary>utils/report_utils.py:841–842</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_utils.py#L841-L842)  
**Lines:** 841–842

**Current**

```python
        if port in avoid:
            continue
```

**Alternative**

```python
        if port in avoid_lookup:
            continue
```

</details>

[Back to contents](#contents)

<a id="m06"></a>

## M06. Use set membership for Docker container-name collisions

**Small saving.** The name collision loop searches a list of existing container names repeatedly.

**Compatibility:** Retain the existing client creation, container listing, random suffix generation, and length limit. The likely benefit is small unless the account has many containers or repeated collisions.

<details>
<summary>core/docker_support.py:214</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/docker_support.py#L214)  
**Lines:** 214

**Current**

```python
        existing_names = [x.name for x in self._client.from_env().containers.list()]
```

**Proposed**

```python
        existing_names = {x.name for x in self._client.from_env().containers.list()}
```

</details>

[Back to contents](#contents)

<a id="m07"></a>

## M07. Clean the weak-reference registry when entries expire

**Behavior-sensitive.** add_template_object scans all registered templates on every insertion.

**Compatibility:** A weakref callback changes when dead dictionary entries disappear, and template_lookup is observable. Preserve its dictionary-of-callable-weakrefs representation. The callback must not remove a newer object that reused the GUID.

<details>
<summary>utils/report_objects.py:384–392</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L384-L392)  
**Lines:** 384–392

Existing dead entries and public registry-inspection behavior need an explicit transition policy.

**Current**

```python
    @classmethod
    def add_template_object(cls, obj):
        # take the opportunity here to clean up the hash
        # of stale entries...
        for guid in list(cls.template_lookup.keys()):
            if cls.template_lookup[guid]() is None:
                del cls.template_lookup[guid]
        # add the new object
        cls.template_lookup[obj.guid] = weakref.ref(obj)
```

**Alternative**

```python
    @classmethod
    def add_template_object(cls, obj):
        guid = obj.guid
        registry = cls.template_lookup

        def remove_expired(reference):
            if registry.get(guid) is reference:
                del registry[guid]

        registry[guid] = weakref.ref(obj, remove_expired)
```

</details>

[Back to contents](#contents)

<a id="m08"></a>

## M08. Avoid duplicate template-property decoding during base-class dispatch

**Behavior-sensitive.** Template._from_db dispatches to a concrete subclass, which hydrates properties, then the outer call reads properties again even when its own property list is empty.

**Compatibility:** Skipping the second get_property changes custom getter calls and malformed-parameter error behavior. Keep this deferred until those hooks are accounted for.

<details>
<summary>serverless/template.py:283–288</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/serverless/template.py#L283-L288)  
**Lines:** 283–288

**Current**

```python
        # Hydrate :attr:`_properties` fields from the stored property dict.
        props = obj.get_property()
        for prop in cls._properties:
            if prop in props:
                setattr(obj, prop, props[prop])
        return obj
```

**Alternative**

```python
        if cls._properties:
            props = obj.get_property()
            for prop in cls._properties:
                if prop in props:
                    setattr(obj, prop, props[prop])
        return obj
```

</details>

[Back to contents](#contents)

<a id="m09"></a>

## M09. Expand only newly discovered templates during REST copying

**Behavior-sensitive.** Each expansion round revisits every template collected so far and calls reorder_children again.

**Compatibility:** Retain visited/attempted GUID handling, successful-object order, missing-object behavior, and save passes. Custom reorder hooks and changing relationships can observe fewer calls. Compare traversal order before using a frontier.

<details>
<summary>utils/report_remote_server.py:752–769</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_remote_server.py#L752-L769)  
**Lines:** 752–769

**Current**

```python
            while True:
                add_set = set()
                for o in copy_list:
                    if o.parent:
                        if o.parent not in copy_set:
                            add_set.add(o.parent)
                    o.reorder_children()
                    for c in o.children:
                        if c not in copy_set:
                            add_set.add(c)
                # are we done?
                if len(add_set) == 0:
                    break
                for guid in add_set:
                    obj = source.get_object_from_guid(guid, objtype=report_objects.TemplateREST)
                    if obj:
                        copy_list.append(obj)
                    copy_set.add(guid)  # we at least tried, so avoid infinite loop...
```

**Alternative**

```python
            frontier = list(copy_list)
            while True:
                add_set = set()
                for o in frontier:
                    if o.parent:
                        if o.parent not in copy_set:
                            add_set.add(o.parent)
                    o.reorder_children()
                    for c in o.children:
                        if c not in copy_set:
                            add_set.add(c)
                # are we done?
                if len(add_set) == 0:
                    break
                next_frontier = []
                for guid in add_set:
                    obj = source.get_object_from_guid(guid, objtype=report_objects.TemplateREST)
                    if obj:
                        copy_list.append(obj)
                        next_frontier.append(obj)
                    copy_set.add(guid)  # we at least tried, so avoid infinite loop...
                frontier = next_frontier
```

</details>

[Back to contents](#contents)

<a id="m10"></a>

## M10. Build tuples directly from ordinary sets during JSON encoding

**Small saving.** The iterable fallback forwards every element through a Python generator before building a tuple. Ordinary sets can supply the tuple directly.

**Compatibility:** Restrict this to exact `set` and `frozenset` objects; retain their iteration order and object references. Keep the existing branch order. Arbitrary iterables retain the generator because `tuple(obj)` can call a custom `__len__` or length hint that the current path does not call.

<details>
<summary>utils/encoders.py:64–65</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/encoders.py#L64-L65)  
**Lines:** 64–65

**Current**

```python
        elif hasattr(obj, "__iter__"):
            return tuple(item for item in obj)
```

**Proposed**

```python
        elif hasattr(obj, "__iter__"):
            if type(obj) is set or type(obj) is frozenset:
                return tuple(obj)
            return tuple(item for item in obj)
```

</details>

[Back to contents](#contents)

<a id="p01"></a>

## P01. Index ordered children in the installed product

**Product change.** The installed get_ordered_children performs a nested search and repeatedly converts child GUIDs to lowercase strings.

**Compatibility:** This belongs to the installed product, outside core. The proposal preserves first-match semantics, duplicate entries in children_order, missing GUID handling and guids_only results. Do not patch an installation as part of a client optimization.

<details>
<summary>reports/models.py:65–78</summary>

**Installed product source:** `django/reports/models.py`  
**Lines:** 65–78

**Current**

```python
    def get_ordered_children(self, guids_only=False):
        sorted_guids = self.children_order.lower().split(',')
        children = list(Template.objects.filter(parent=self))
        # return the children based on the order of guids in children_order
        ordered_children = []
        for guid in sorted_guids:
            for idx, child in enumerate(children):
                if guid == str(child.guid).lower():
                    if guids_only:
                        ordered_children.append(child.guid)
                    else:
                        ordered_children.append(child)
                    break
        return ordered_children
```

**Alternative**

```python
    def get_ordered_children(self, guids_only=False):
        sorted_guids = self.children_order.lower().split(',')
        children = list(Template.objects.filter(parent=self))
        children_by_guid = {}
        for child in children:
            children_by_guid.setdefault(str(child.guid).lower(), child)
        ordered_children = []
        for guid in sorted_guids:
            child = children_by_guid.get(guid)
            if child is not None:
                ordered_children.append(child.guid if guids_only else child)
        return ordered_children
```

</details>

[Back to contents](#contents)

<a id="p02"></a>

## P02. Address product-owned child queries during engine construction

**Product change.** get_engine recursively calls get_ordered_children, which issues Template.objects.filter(parent=self) at every node. Prefetching client proxies does not affect that explicit query.

**Compatibility:** Using the reverse relation would allow an ORM prefetch cache to be consumed, but database routing and supported tree-loading strategy must first be settled. This line alone does not eliminate recursive queries; supported product integration is required.

<details>
<summary>reports/models.py:65–67</summary>

**Installed product source:** `django/reports/models.py`  
**Lines:** 65–67

Conditional product-side prerequisite. The remaining ordering code is unchanged.

**Current**

```python
    def get_ordered_children(self, guids_only=False):
        sorted_guids = self.children_order.lower().split(',')
        children = list(Template.objects.filter(parent=self))
```

**Alternative**

```python
    def get_ordered_children(self, guids_only=False):
        sorted_guids = self.children_order.lower().split(',')
        children = list(self.children.all())
```

</details>

<details>
<summary>reports/models.py:84–94</summary>

**Installed product source:** `django/reports/models.py`  
**Lines:** 84–94

Retain recursive engine construction until the product provides a supported preloaded-tree path.

**Current**

```python
    def get_engine(self):
        # create the object
        engine = TemplateEngine.factory(self)
        for child in self.get_ordered_children():
            # for each child template, get the engine
            child_engine = child.get_engine()
            # add child engine to the parent engine
            engine.add_child(child_engine)
            # set the parent
            child_engine.set_parent(engine)
        return engine
```

**Keep the current code** to preserve the compatibility requirements above.

</details>

[Back to contents](#contents)

<a id="r01"></a>

## R01. Retain serialization formats and numerical semantics

**Keep current behavior.** New pickle protocols, different dtypes, and replacement numerical reductions can look faster but alter data compatibility or results.

**Compatibility:** Keep protocol=0, current encodings, NaN treatment, signed-zero behavior and normalization operation order. The code below is the compatibility boundary, not an optimization proposal.

<details>
<summary>serverless/item.py:385</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/serverless/item.py#L385)  
**Lines:** 385

Protocol-0 serialization used by file-free payloads.

**Current**

```python
        self._orm_instance.payloaddata = pickle.dumps(self.content, protocol=0)
```

**Keep the current code** to preserve the compatibility requirements above.

</details>

<details>
<summary>utils/report_objects.py:160–179</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/report_objects.py#L160-L179)  
**Lines:** 160–179

Replacing Python min/max with NumPy reductions changes some NaN and signed-zero cases.

**Current**

```python
def extract_data_from_ensight_query(q):
    data = q.QUERY_DATA
    array = numpy.array(data["xydata"], numpy.double).transpose()
    if q.NORMALIZEX:
        tmp = array[0] - min(array[0])
        mx = max(tmp)
        if mx != 0.0:
            tmp /= mx
        array[0] = tmp
    else:
        array[0] = array[0] * q.SCALE[0] + q.OFFSET[0]
    if q.NORMALIZEY:
        tmp = array[1] - min(array[1])
        mx = max(tmp)
        if mx != 0.0:
            tmp /= mx
        array[1] = tmp
    else:
        array[1] = array[1] * q.SCALE[1] + q.OFFSET[1]
    return array
```

**Keep the current code** to preserve the compatibility requirements above.

</details>

[Back to contents](#contents)

<a id="r02"></a>

## R02. Retain browser readiness, render isolation and dynamic viewer assets

**Keep current behavior.** Skipping readiness phases, reusing browser state, or copying only assets visible in the initial HTML can reduce work while changing exported output.

**Compatibility:** Preserve page layout, font/MathJax/plot readiness, browser context isolation, inline size thresholds, filename rewrites, and the runtime-loaded asset inventory. The local exporter copies the selected MathJax branch and silently attempts the other branch; the remote exporter downloads only the selected branch. Retain that output difference. Parallel asset work can reorder collision suffixes, cumulative inline-budget decisions, warnings, and failures. Do not parallelize those operations or add browser-global API interception.

<details>
<summary>utils/pdf_renderer.py:472–493</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/pdf_renderer.py#L472-L493)  
**Lines:** 472–493

Browser/context creation establishes the current isolation boundary.

**Current**

```python
            with self._playwright_browser_binary_env(), sync_playwright() as playwright:
                self._logger.info("Launching headless Chromium for browser PDF export.")
                browser = playwright.chromium.launch(
                    headless=True,
                    timeout=self._remaining_browser_phase_timeout_ms(
                        browser_phase_deadline, "browser launch"
                    ),
                )
                context = None

                try:
                    self._remaining_browser_phase_timeout_ms(
                        browser_phase_deadline, "browser context creation"
                    )
                    # Fix the responsive layout width up front so Plotly and other browser-rendered
                    # items lay themselves out deterministically before the PDF width is computed.
                    context = self._new_browser_context(browser)
                    self._prepare_context(context)
                    self._remaining_browser_phase_timeout_ms(
                        browser_phase_deadline, "page creation"
                    )
                    page = context.new_page()
```

**Keep the current code** to preserve the compatibility requirements above.

</details>

<details>
<summary>utils/pdf_renderer.py:510–517</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/pdf_renderer.py#L510-L517)  
**Lines:** 510–517

Readiness precedes width measurement.

**Current**

```python
                    # Force screen media so the PDF matches the browser view instead of print CSS.
                    page.emulate_media(media="screen")
                    self._apply_pdf_capture_styles(page)
                    self._wait_for_render_ready(page, deadline=browser_phase_deadline)
                    self._remaining_browser_phase_timeout_ms(
                        browser_phase_deadline, "PDF width measurement"
                    )
                    pdf_width = self._compute_pdf_width(page)
```

**Keep the current code** to preserve the compatibility requirements above.

</details>

<details>
<summary>serverless/html_exporter.py:370–394</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/serverless/html_exporter.py#L370-L394)  
**Lines:** 370–394

Viewer and Draco files are needed by URLs constructed at runtime.

**Current**

```python
        # --- Modern viewer payload kept under ./ansys{ver}/... ---
        self._copy_static_files(
            VIEWER_UTILS,
            f"ansys{self._ansys_version}/nexus/utils/",
            f"ansys{self._ansys_version}/nexus/utils/",
        )
        self._copy_static_files(
            VIEWER_JS, f"ansys{self._ansys_version}/nexus/", f"ansys{self._ansys_version}/nexus/"
        )
        self._copy_legacy_context_menu_assets()
        self._copy_static_files(
            THREE_JS,
            f"ansys{self._ansys_version}/nexus/threejs/",
            f"ansys{self._ansys_version}/nexus/threejs/",
        )
        self._copy_static_files(
            DRACO_JS,
            f"ansys{self._ansys_version}/nexus/threejs/libs/draco/",
            f"ansys{self._ansys_version}/nexus/threejs/libs/draco/",
        )
        self._copy_static_files(
            DRACO_JS,
            f"ansys{self._ansys_version}/nexus/threejs/libs/draco/gltf/",
            f"ansys{self._ansys_version}/nexus/threejs/libs/draco/gltf/",
        )
```

**Keep the current code** to preserve the compatibility requirements above.

</details>

[Back to contents](#contents)

<a id="r03"></a>

## R03. Retain observable I/O ordering in downloads and archive extraction

**Keep current behavior.** The example downloader probes the remote URL before its cache check. Docker copying stages a tar archive before extracting it. Removing those steps changes error or partial-output behavior.

**Compatibility:** Do not remove the example URL check merely because a local file exists. Do not stream extraction or asset writes without defining partial-file, error, archive and source-equals-target behavior.

<details>
<summary>examples/downloads.py:170–173</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/examples/downloads.py#L170-L173)  
**Lines:** 170–173

A cached example still follows remote-existence validation.

**Current**

```python
    url = _get_file_url(file_name, directory)
    if not check_url_exists(url):
        raise RemoteFileNotFoundError(url)
    return _retrieve_file(url, file_name, save_path)
```

**Keep the current code** to preserve the compatibility requirements above.

</details>

<details>
<summary>core/docker_support.py:146–164</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/docker_support.py#L146-L164)  
**Lines:** 146–164

Staging and extraction have separate failure boundaries.

**Current**

```python
    def copy_to_host(self, src: str, *, dest: str = ".") -> None:
        try:
            tar_stream, _ = self._container.get_archive(src)
            # Ensure the output directory exists
            output_path = Path(dest)
            output_path.mkdir(parents=True, exist_ok=True)
            # Save the tar archive
            tar_file_path = output_path / f"{self._container.id}.tar"
            with tar_file_path.open("wb") as tar_file:
                for chunk in tar_stream:
                    tar_file.write(chunk)
            # Extract the tar archive
            with tarfile.open(tar_file_path) as tar:
                tar.extractall(path=output_path)  # nosec B202
            # Remove the tar archive
            with suppress(OSError):
                tar_file_path.unlink()
        except Exception as e:
            raise RuntimeError(f"Can't copy files from container: {src}\n\n{str(e)}")
```

**Keep the current code** to preserve the compatibility requirements above.

</details>

[Back to contents](#contents)

<a id="r04"></a>

## R04. Defer caches for mutable model metadata and mesh/render state

**Keep current behavior.** Model field/property introspection is repeated; enhanced-image generation also obtains metadata and converts meshes for each variable.

**Compatibility:** Permanent metadata caches can miss dynamic class changes. Mesh reuse must account for append_field_to_grid, vector trimming, VTK ownership and per-variable mutations. Retain the current code to preserve those contracts.

<details>
<summary>serverless/base.py:382–396</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/serverless/base.py#L382-L396)  
**Lines:** 382–396

Metadata currently reflects the class and ORM model at each call.

**Current**

```python
    @staticmethod
    def _get_orm_field_names(orm_instance):
        """Return the list of ORM field names for the given instance."""
        return tuple(f.name for f in orm_instance._meta.get_fields())

    @classmethod
    def _get_field_names(cls, with_types=False, include_private=False):
        """Return the dataclass field names (and optionally types)."""
        fields_ = []
        for f in dataclass_fields(cls):
            if not include_private and f.name.startswith("_"):
                continue
            fields_.append((f.name, f.type) if with_types else f.name)
        return tuple(fields_)
```

**Keep the current code** to preserve the compatibility requirements above.

</details>

<details>
<summary>serverless/base.py:407–413</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/serverless/base.py#L407-L413)  
**Lines:** 407–413

Property discovery currently includes dynamically visible class properties.

**Current**

```python
    def _get_prop_field_names(cls):
        """Return all property names defined on the class."""
        property_fields = []
        for name, value in inspect.getmembers(cls):
            if isinstance(value, property):
                property_fields.append(name)
        return tuple(property_fields)
```

**Keep the current code** to preserve the compatibility requirements above.

</details>

<details>
<summary>utils/enhanced_images.py:526–548</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/utils/enhanced_images.py#L526-L548)  
**Lines:** 526–548

Mesh/field assembly participates in later variable-specific mutations.

**Current**

```python
            dpf_unit_system = model.metadata.result_info.unit_system_name
            unit_system_to_name = dpf_unit_system.split(":", 1)[0]
            meshed_region = model.metadata.meshed_region  # Whole mesh region
            json_data_variables.append(
                {
                    "name": var_name,
                    "id": "3456",  # Todo: optimize hardcoded part ID
                    "pal_id": "1",  # colorby_var_int,
                    "unit_dims": "",
                    "unit_system_to_name": unit_system_to_name,
                    "unit_label": var_unit,
                }
            )

            # Convert DPF to a pyvista UnstructuredGrid, which inherits from vtk
            grid = vtk_helper.dpf_mesh_to_vtk(meshed_region)
            # Add variable data
            grid = vtk_helper.append_field_to_grid(var_field, meshed_region, grid, var_name)

            geometry_filter = vtk.vtkGeometryFilter()
            geometry_filter.SetInputData(grid)
            geometry_filter.Update()
            poly_data = geometry_filter.GetOutput()
```

**Keep the current code** to preserve the compatibility requirements above.

</details>

[Back to contents](#contents)

<a id="r05"></a>

## R05. Retain eager object collections and ordinary save semantics

**Keep current behavior.** Lazy ObjectSet conversion and bulk inserts could reduce allocations and database round trips but would change when objects are loaded, validated and saved.

**Compatibility:** Keep eager materialization, independent proxy construction, per-object saves and their hooks. Setup, migrations, locks, retries and cleanup are also outside the narrow optimization candidates.

<details>
<summary>serverless/base.py:859–866</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/serverless/base.py#L859-L866)  
**Lines:** 859–866

Objects are materialized during collection construction.

**Current**

```python
    def __post_init__(self):
        """Materialize ORM instances into :class:`BaseModel` objects."""
        if self._orm_queryset is None:
            return
        self._saved = True
        self._obj_set = [
            self._model._from_db(instance, parent=self._parent) for instance in self._orm_queryset
        ]
```

**Keep the current code** to preserve the compatibility requirements above.

</details>

<details>
<summary>serverless/adr.py:2094–2101</summary>

[Pinned source](https://github.com/ansys/pydynamicreporting/blob/2f6d0fc9364b76f557a8dcd59568b0e79124210e/src/ansys/dynamicreporting/core/serverless/adr.py#L2094-L2101)  
**Lines:** 2094–2101

Per-object save order is part of the existing behavior.

**Current**

```python
        for obj in objects:
            # When copying across databases, reset the object's DB if needed.
            if obj.db and kwargs.get("using", "default") != obj.db:  # pragma: no cover
                # required if copying across databases
                obj.reinit()
            obj.save(**kwargs)
            count += 1
        return count
```

**Keep the current code** to preserve the compatibility requirements above.

</details>

[Back to contents](#contents)
