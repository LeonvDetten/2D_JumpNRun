// Getting files in and out: the iOS share sheet ("In Dateien sichern", AirDrop, Mail ...) or a download,
// and the file picker. Must be called from a tap (user gesture).

export async function shareText(filename: string, content: string, mime = "text/plain"): Promise<boolean> {
  const file = new File([content], filename, { type: mime });
  try {
    if (navigator.canShare?.({ files: [file] })) {
      await navigator.share({ files: [file], title: filename });
      return true;
    }
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") return false;
    // fall back to a download
  }
  try {
    const url = URL.createObjectURL(file);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10_000);
    return true;
  } catch {
    return false;
  }
}

export function pickTextFile(accept: string): Promise<string | null> {
  return new Promise((resolve) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = accept;
    input.style.display = "none";
    let done = false;
    const finish = (v: string | null) => {
      if (done) return;
      done = true;
      input.remove();
      resolve(v);
    };
    input.addEventListener("change", () => {
      const f = input.files?.[0];
      if (!f) finish(null);
      else f.text().then(finish, () => finish(null));
    });
    input.addEventListener("cancel", () => finish(null));
    document.body.appendChild(input);
    input.click();
  });
}
