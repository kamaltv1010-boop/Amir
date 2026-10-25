// Compiles TrackerRules.json with WebKit's own content blocker compiler, the
// same one the app uses, so invalid rules fail CI instead of silently turning
// tracker blocking off on the phone. Usage: swift check_tracker_rules.swift FILE
import Foundation
import WebKit

let path = CommandLine.arguments[1]
let rules = try String(contentsOfFile: path, encoding: .utf8)
WKContentRuleListStore.default().compileContentRuleList(
    forIdentifier: "ci-check",
    encodedContentRuleList: rules
) { list, error in
    if let error {
        print("::error::\(path) does not compile: \(error)")
        exit(1)
    }
    print("\(path) compiled: \(list != nil ? "ok" : "no list")")
    exit(list != nil ? 0 : 1)
}
RunLoop.main.run(until: Date(timeIntervalSinceNow: 120))
print("::error::Compiling \(path) timed out")
exit(1)
