import CoreAudio
import Foundation
let main = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "BuiltInSpeakerDevice"
let desc: [String: Any] = [
  kAudioAggregateDeviceNameKey: "直播多输出",
  kAudioAggregateDeviceUIDKey: "qqlive-multiout",
  kAudioAggregateDeviceIsStackedKey: 1,
  kAudioAggregateDeviceMainSubDeviceKey: main,
  kAudioAggregateDeviceSubDeviceListKey: [
    [kAudioSubDeviceUIDKey: main],
    [kAudioSubDeviceUIDKey: "BlackHole2ch_UID", kAudioSubDeviceDriftCompensationKey: 1],
  ],
]
var id = AudioObjectID(0)
let st = AudioHardwareCreateAggregateDevice(desc as CFDictionary, &id)
print("status", st, "id", id)
