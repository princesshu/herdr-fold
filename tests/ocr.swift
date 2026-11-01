// The text in every frame of each image named on the command line (an animation's frames one by one), as JSON lines:
// {"file": …, "frame": n, "text": …}, by macOS's own text recognition (Vision). test_privacy.py compiles and runs it.
// --draw TEXT FILE: TEXT drawn on a white PNG, for the test that the recognition reads what an image shows.
import AppKit
import Foundation
import ImageIO
import Vision

let arguments = CommandLine.arguments
if arguments.count == 4 && arguments[1] == "--draw" {
    let image = NSImage(size: NSSize(width: 900, height: 80))
    image.lockFocus()
    NSColor.white.setFill()
    NSRect(x: 0, y: 0, width: 900, height: 80).fill()
    (arguments[2] as NSString).draw(at: NSPoint(x: 10, y: 25),
                                    withAttributes: [.font: NSFont.monospacedSystemFont(ofSize: 28, weight: .regular)])
    image.unlockFocus()
    guard let tiff = image.tiffRepresentation, let png = NSBitmapImageRep(data: tiff)?.representation(using: .png,
                                                                                                    properties: [:]),
          (try? png.write(to: URL(fileURLWithPath: arguments[3]))) != nil else { exit(1) }
    exit(0)
}

for path in arguments.dropFirst() {
    guard let source = CGImageSourceCreateWithURL(URL(fileURLWithPath: path) as CFURL, nil) else { continue }
    for frame in 0..<CGImageSourceGetCount(source) {
        guard let image = CGImageSourceCreateImageAtIndex(source, frame, nil) else { continue }
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.usesLanguageCorrection = false              // a path or an address is no word to correct
        try? VNImageRequestHandler(cgImage: image, options: [:]).perform([request])
        let lines = (request.results ?? []).compactMap { $0.topCandidates(1).first?.string }
        let record: [String: Any] = ["file": path, "frame": frame, "text": lines.joined(separator: "\n")]
        if let data = try? JSONSerialization.data(withJSONObject: record),
           let line = String(data: data, encoding: .utf8) {
            print(line)
        }
    }
}
