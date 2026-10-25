"""Bundle the offline viewer without installing any dependencies."""

import argparse
from pathlib import Path


def bundle():
    root = Path(__file__).resolve().parent
    html = (root / "index.html").read_text(encoding="utf-8")
    for name in ("model.js", "demo.js", "app.js"):
        code = (root / name).read_text(encoding="utf-8").replace("</script", "<\\/script")
        tag = f'<script src="{name}"></script>'
        if html.count(tag) != 1:
            raise ValueError(f"Expected one script reference: {name}")
        html = html.replace(tag, "<script>\n" + code + "\n</script>")
    tag = '<link rel="stylesheet" href="style.css" />'
    if html.count(tag) != 1:
        raise ValueError("Expected one style reference")
    css = (root / "style.css").read_text(encoding="utf-8")
    return html.replace(tag, "<style>\n" + css + "\n</style>").replace(
        'href="index.html"', 'href="#"'
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    content = bundle()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(content)
    print(args.output)


if __name__ == "__main__":
    main()
