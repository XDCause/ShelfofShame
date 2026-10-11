// Read a product barcode (EAN-13 / EAN-8 / UPC) from a photo, entirely in the browser.
// Nothing is sent anywhere: the photo is decoded on the phone itself.

const FORMATS = ['ean_13', 'ean_8', 'upc_a', 'upc_e']

export async function readBarcode(file) {
  const bitmap = await createImageBitmap(file)
  try {
    // 1. The browser's built-in detector, where it exists (Chrome on Android): fast and good
    //    with angled or small barcodes.
    if ('BarcodeDetector' in window) {
      try {
        const supported = await window.BarcodeDetector.getSupportedFormats()
        const formats = FORMATS.filter((f) => supported.includes(f))
        if (formats.length) {
          const found = await new window.BarcodeDetector({ formats }).detect(bitmap)
          if (found.length) return found[0].rawValue
        }
      } catch {
        // fall through to ZXing
      }
    }

    // 2. ZXing, which works in every browser (including iPhone Safari). It's ~400 KB, so it's
    //    loaded only the first time you scan rather than with the rest of the app.
    const zx = await import('@zxing/library')
    const hints = new Map([
      [zx.DecodeHintType.POSSIBLE_FORMATS, [zx.BarcodeFormat.EAN_13, zx.BarcodeFormat.EAN_8,
        zx.BarcodeFormat.UPC_A, zx.BarcodeFormat.UPC_E]],
      [zx.DecodeHintType.TRY_HARDER, true],
    ])
    const reader = new zx.MultiFormatReader()
    // Phone photos are big and the barcode may be small or sideways, so try a few sizes and
    // both orientations (ZXing reads bars left-to-right).
    for (const maxSide of [1600, 1000, 640]) {
      for (const rotate of [0, 90]) {
        const canvas = draw(bitmap, maxSide, rotate)
        try {
          const source = new zx.HTMLCanvasElementLuminanceSource(canvas)
          return reader.decode(new zx.BinaryBitmap(new zx.HybridBinarizer(source)), hints).getText()
        } catch {
          // not found at this size/rotation; try the next
        }
      }
    }
    return null
  } finally {
    bitmap.close?.()
  }
}

function draw(bitmap, maxSide, rotate) {
  const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height))
  const w = Math.round(bitmap.width * scale)
  const h = Math.round(bitmap.height * scale)
  const canvas = document.createElement('canvas')
  canvas.width = rotate ? h : w
  canvas.height = rotate ? w : h
  const ctx = canvas.getContext('2d')
  if (rotate) {
    ctx.translate(h, 0)
    ctx.rotate(Math.PI / 2)
  }
  ctx.drawImage(bitmap, 0, 0, w, h)
  return canvas
}
