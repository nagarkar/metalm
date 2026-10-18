// Draws the SuperLM notifier's icon (a 1024-point PNG): the house purple-to-pink
// tile with a bold white "S" and a small green spark, generic to every *lm repo.
// Run by build.sh with the output path as its one argument.
// An app's icon is the same picture with its own letter and gradient (make_brand.py):
//   swift make_icon.swift out.png T 3f73fa 5940d9
import AppKit

let args = CommandLine.arguments
func rgb(_ hex: String) -> NSColor {
    let v = Int(hex, radix: 16)!
    return NSColor(srgbRed: CGFloat((v >> 16) & 255) / 255, green: CGFloat((v >> 8) & 255) / 255,
                   blue: CGFloat(v & 255) / 255, alpha: 1)
}
let letter = args.count > 2 ? args[2] : "S"

let size: CGFloat = 1024
let image = NSImage(size: NSSize(width: size, height: size))
image.lockFocus()
let ctx = NSGraphicsContext.current!.cgContext

// The tile: macOS icon grid (824 inset by 100), bright purple to pink.
let tile = CGRect(x: 100, y: 100, width: 824, height: 824)
ctx.addPath(CGPath(roundedRect: tile, cornerWidth: 185, cornerHeight: 185, transform: nil))
ctx.clip()
let from = args.count > 4 ? rgb(args[3]) : NSColor(srgbRed: 0.55, green: 0.30, blue: 0.95, alpha: 1)
let to = args.count > 4 ? rgb(args[4]) : NSColor(srgbRed: 0.93, green: 0.36, blue: 0.75, alpha: 1)
let colors = [from.cgColor, to.cgColor] as CFArray
let gradient = CGGradient(colorsSpace: CGColorSpace(name: CGColorSpace.sRGB), colors: colors,
                          locations: [0, 1])!
ctx.drawLinearGradient(gradient, start: CGPoint(x: 100, y: 924), end: CGPoint(x: 924, y: 100), options: [])

// A bold white letter, centred, no wider than the S so it clears the spark.
func glyph(_ s: String, _ points: CGFloat) -> NSAttributedString {
    NSAttributedString(string: s, attributes: [
        .font: NSFont.systemFont(ofSize: points, weight: .black), .foregroundColor: NSColor.white,
    ])
}
let box = NSSize(width: size, height: size)
let sWidth = glyph("S", 640).boundingRect(with: box, options: [.usesLineFragmentOrigin]).width
let wide = glyph(letter, 640).boundingRect(with: box, options: [.usesLineFragmentOrigin]).width
let text = glyph(letter, 640 * min(1, sWidth / wide))
let bounds = text.boundingRect(with: box, options: [.usesLineFragmentOrigin])
text.draw(at: NSPoint(x: (size - bounds.width) / 2 - 10, y: (size - bounds.height) / 2 - 20))

// A four-point spark in bright green, top right: something happened.
let green = NSColor(srgbRed: 0.30, green: 1.0, blue: 0.55, alpha: 1)
green.setFill()
let c = NSPoint(x: 760, y: 760)
let spark = NSBezierPath()
let long: CGFloat = 110, short: CGFloat = 26
spark.move(to: NSPoint(x: c.x, y: c.y + long))
spark.line(to: NSPoint(x: c.x + short, y: c.y + short))
spark.line(to: NSPoint(x: c.x + long, y: c.y))
spark.line(to: NSPoint(x: c.x + short, y: c.y - short))
spark.line(to: NSPoint(x: c.x, y: c.y - long))
spark.line(to: NSPoint(x: c.x - short, y: c.y - short))
spark.line(to: NSPoint(x: c.x - long, y: c.y))
spark.line(to: NSPoint(x: c.x - short, y: c.y + short))
spark.close()
spark.fill()

image.unlockFocus()
let rep = NSBitmapImageRep(data: image.tiffRepresentation!)!
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: args[1]))
