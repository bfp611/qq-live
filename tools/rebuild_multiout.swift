import CoreAudio
import Foundation
var addr = AudioObjectPropertyAddress(mSelector: kAudioHardwarePropertyTranslateUIDToDevice, mScope: kAudioObjectPropertyScopeGlobal, mElement: kAudioObjectPropertyElementMain)
var uid: CFString = "qqlive-multiout" as CFString
var dev = AudioObjectID(0); var sz = UInt32(MemoryLayout<AudioObjectID>.size)
let s0 = withUnsafePointer(to: &uid) { AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &addr, UInt32(MemoryLayout<CFString>.size), $0, &sz, &dev) }
if s0 == 0 && dev != 0 { print("destroy", AudioHardwareDestroyAggregateDevice(dev)) }
let main = CommandLine.arguments[1]
let desc: [String: Any] = [
  kAudioAggregateDeviceNameKey: "直播多输出", kAudioAggregateDeviceUIDKey: "qqlive-multiout",
  kAudioAggregateDeviceIsStackedKey: 1, kAudioAggregateDeviceMainSubDeviceKey: main,
  kAudioAggregateDeviceSubDeviceListKey: [[kAudioSubDeviceUIDKey: main],
    [kAudioSubDeviceUIDKey: "BlackHole2ch_UID", kAudioSubDeviceDriftCompensationKey: 1]]]
var id = AudioObjectID(0)
print("create", AudioHardwareCreateAggregateDevice(desc as CFDictionary, &id), id)
