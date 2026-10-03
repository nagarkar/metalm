// Draws the SuperLM notifier's icon (a 1024-point PNG): the house purple-to-pink
// tile with a bold white "S" and a small green spark, generic to every *lm repo.
// Run by build.sh with the output path as its one argument.
import AppKit

let size: CGFloat = 1024
let image = NSImage(size: NSSize(width: size, height: size))
image.lockFocus()
let ctx = NSGraphicsContext.current!.cgContext

// The tile: macOS icon grid (824 inset by 100), bright purple to pink.
let tile = CGRect(x: 100, y: 100, width: 824, height: 824)
ctx.addPath(CGPath(roundedRect: tile, cornerWidth: 185, cornerHeight: 185, transform: nil))
ctx.clip()
let colors = [NSColor(srgbRed: 0.55, green: 0.30, blue: 0.95, alpha: 1).cgColor,
              NSColor(srgbRed: 0.93, green: 0.36, blue: 0.75, alpha: 1).cgColor] as CFArray
let gradient = CGGradient(colorsSpace: CGColorSpace(name: CGColorSpace.sRGB), colors: colors,
                          locations: [0, 1])!
ctx.drawLinearGradient(gradient, start: CGPoint(x: 100, y: 924), end: CGPoint(x: 924, y: 100), options: [])

// A bold white S, centred.
let font = NSFont.systemFont(ofSize: 640, weight: .black)
let text = NSAttributedString(string: "S", attributes: [
    .font: font, .foregroundColor: NSColor.white,
])
let bounds = text.boundingRect(with: NSSize(width: size, height: size), options: [.usesLineFragmentOrigin])
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
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: CommandLine.arguments[1]))
