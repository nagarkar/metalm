// SuperLM Notifier: posts one macOS notification for any *lm repo, under the
// SuperLM name and icon, then quits. Repos call bin/superlm-notify, never this.
//
//   open -n "SuperLM Notifier.app" --args --repo R --body B [--title T] --status-file F
//
// The banner's title names the repo ("tradelm", or "tradelm · Nightly job" with a
// --title) and its text is the message. It must be launched as an app (`open`):
// macOS grants notifications only to an app LaunchServices started. `open` cannot
// pass an exit code back, so the result goes to --status-file: "ok", or why the
// banner was not shown. The first launch asks the owner once to allow it.
import Foundation
import UserNotifications

func arg(_ name: String) -> String? {
    let args = CommandLine.arguments
    guard let i = args.firstIndex(of: name), i + 1 < args.count else { return nil }
    return args[i + 1]
}

func finish(_ code: Int32, _ message: String) -> Never {
    if let path = arg("--status-file") {
        try? (message + "\n").write(toFile: path, atomically: true, encoding: .utf8)
    }
    exit(code)
}

guard let repo = arg("--repo"), let body = arg("--body") else {
    finish(2, "usage: --repo R --body B [--title T] --status-file F")
}
let title = arg("--title").map { "\(repo) · \($0)" } ?? repo
let center = UNUserNotificationCenter.current()
let done = DispatchSemaphore(value: 0)
var code: Int32 = 1
var reason = "no answer from macOS"

center.requestAuthorization(options: [.alert, .sound]) { granted, error in
    guard granted else {
        reason = "notifications not allowed for SuperLM (System Settings → Notifications): "
            + (error?.localizedDescription ?? "denied")
        done.signal(); return
    }
    let content = UNMutableNotificationContent()
    content.title = title
    content.body = body
    content.sound = .default
    center.add(UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: nil)) { error in
        code = error == nil ? 0 : 1
        reason = error?.localizedDescription ?? "ok"
        done.signal()
    }
}
// Long enough for the owner to answer the one-time permission prompt.
_ = done.wait(timeout: .now() + 120)
finish(code, code == 0 ? "ok" : reason)
