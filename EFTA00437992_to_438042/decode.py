import base64
import re
import os


EXTENSIONS = {
    "text/plain": "txt",
    "text/html": "html"
}


def decode_all(plaintext_dir, blob_dir, output_dir):

    for filepath in get_plaintext_files(plaintext_dir):
        code = str(re.search(r"(EFTA\d+)_", os.path.split(filepath)[1]).group(1))
        print(f"Processing {code}")
        with open(filepath, "r") as f:
            all_text = "".join([line.rstrip() + "\n" for line in f.readlines()])

        for idx, (content_type, blob) in enumerate(extract_base64_blobs(all_text)):
            print(f"  Found a {content_type} blob (length={len(blob)})")
            if content_type in EXTENSIONS:
                ext = EXTENSIONS[content_type]
                rawfile_name = os.path.join(blob_dir, f"{code}_raw{idx}_{ext}.txt")
                file_name = os.path.join(output_dir, f"{code}.{ext}")
            else:
                rawfile_name = os.path.join(blob_dir, f"{code}_raw{idx}.txt")
                file_name = None

            with open(rawfile_name, "w") as f:
                f.write(blob)
                print(f"    Wrote: {rawfile_name}")

            if file_name is not None:
                blob = blob.replace("\n", "").replace(" ", "")
                decoded = base64.b64decode(blob)
                with open(file_name, "wb") as f:
                    f.write(decoded)
                print(f"    Wrote: {file_name}")


def get_plaintext_files(plaintext_dir):
    for fname in os.listdir(plaintext_dir):
        if fname.endswith("plaintext.txt"):
            yield os.path.join(plaintext_dir, fname)


def extract_base64_blobs(text: str):
    ret = []
    regex = r"Content-Type: (.*);.*\n(?:.*\n)*\n((?:[a-zA-Z\/+=0-9]+\n)+)"
    found = re.search(regex, text)
    while found is not None:
        ret.append((str(found.group(1)), str(found.group(2))))
        text = text[found.end():]
        found = re.search(regex, text)
    return ret


if __name__ == "__main__":
    decode_all("out_plaintext", "out_extracted_blobs", "output")
