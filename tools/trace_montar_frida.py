#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, sys, time, datetime, traceback
from pathlib import Path

try:
    import frida
except Exception as e:
    print("[ERRO] Python package 'frida' nao esta disponivel:", e)
    print("Execute: py -3 -m pip install --user frida frida-tools")
    raise SystemExit(2)

AGENT = r"""
'use strict';

const STATIC_IMAGE_BASE = ptr('0x00400000');

const RVAS = {
  montar_cb:       0x573C90,
  signal_invoke:   0x536BE0,
  build_car:       0x687960,
  craft_caller:    0x59FF50,
  craft_wrapper:   0x5A4BA0,
  craft_body:      0x5A4BB0,
  craft_result:    0x5A3CA0,
  result_apply:    0x5A3840,
  global_online:   0xBAD9D0
};

const NAMES = {};
Object.keys(RVAS).forEach(k => NAMES[RVAS[k]] = k);

let mod = null;
let base = null;
let end = null;
let traceSeq = 0;
let active = new Map();
let markerHandles = [];

function phex(p) {
  try { return ptr(p).toString(); } catch (_) { return String(p); }
}

function safePtr(p) {
  try { return ptr(p); } catch (_) { return ptr(0); }
}

function safeReadPointer(p) {
  try {
    p = safePtr(p);
    if (p.isNull()) return ptr(0);
    return p.readPointer();
  } catch (_) { return ptr(0); }
}

function safeReadUtf8(p, maxLen) {
  try {
    p = safePtr(p);
    if (p.isNull()) return null;
    return p.readUtf8String(maxLen || 1024);
  } catch (_) { return null; }
}

function safeReadUtf16(p, maxChars) {
  try {
    p = safePtr(p);
    if (p.isNull()) return null;
    return p.readUtf16String(maxChars || 1024);
  } catch (_) { return null; }
}

function addrFromRva(rva) {
  return base.add(rva);
}

function inAms(p) {
  p = safePtr(p);
  return p.compare(base) >= 0 && p.compare(end) < 0;
}

function rvaOf(p) {
  p = safePtr(p);
  if (!inAms(p)) return null;
  return p.sub(base).toUInt32();
}

function markerNameFor(p) {
  const r = rvaOf(p);
  if (r === null) return null;
  for (const k of Object.keys(RVAS)) {
    if (RVAS[k] === r) return k;
  }
  return null;
}

function sendEvent(kind, data) {
  const payload = Object.assign({
    kind: kind,
    ts_ms: Date.now()
  }, data || {});
  send(payload);
}

function snapshotContext(ctx) {
  const out = {};
  for (const k of ['eax','ebx','ecx','edx','esi','edi','esp','ebp','eip']) {
    try { if (ctx[k] !== undefined) out[k] = phex(ctx[k]); } catch (_) {}
  }
  return out;
}

function installMarker(name, rva, opts) {
  const at = addrFromRva(rva);
  try {
    const h = Interceptor.attach(at, {
      onEnter(args) {
        const tid = this.threadId;
        const evt = {
          name: name,
          rva: '0x' + rva.toString(16).toUpperCase(),
          address: phex(at),
          thread_id: tid,
          depth: this.depth,
          return_address: phex(this.returnAddress),
          context: snapshotContext(this.context)
        };

        if (name === 'montar_cb') {
          const ecx = safePtr(this.context.ecx);
          evt.gbbw = phex(ecx);
          evt.signal = phex(safeReadPointer(ecx.add(0x44)));
          evt.signal_ctrl = phex(safeReadPointer(ecx.add(0x48)));
          evt.owner = phex(safeReadPointer(ecx.add(0x04)));
          evt.owner_ctrl = phex(safeReadPointer(ecx.add(0x08)));
          beginTrace(tid, evt);
        } else if (name === 'signal_invoke') {
          const ecx = safePtr(this.context.ecx);
          evt.this_ptr = phex(ecx);
          evt.obj0 = phex(safeReadPointer(ecx));
          evt.obj4 = phex(safeReadPointer(ecx.add(4)));
          evt.obj8 = phex(safeReadPointer(ecx.add(8)));
          try { evt.objC_u32 = ecx.add(0xC).readU32(); } catch (_) { evt.objC_u32 = null; }
        } else if (name === 'build_car' || name === 'craft_caller' ||
                   name === 'craft_wrapper' || name === 'craft_body' ||
                   name === 'craft_result' || name === 'result_apply' ||
                   name === 'global_online') {
          evt.this_ptr = phex(this.context.ecx);
          evt.stack0 = phex(safeReadPointer(this.context.esp));
          evt.stack4 = phex(safeReadPointer(safePtr(this.context.esp).add(4)));
          evt.stack8 = phex(safeReadPointer(safePtr(this.context.esp).add(8)));
        }

        this._montar_evt = evt;
        sendEvent('marker_enter', evt);
      },
      onLeave(retval) {
        const evt = this._montar_evt || {name:name, thread_id:this.threadId};
        evt.retval = phex(retval);
        sendEvent('marker_leave', evt);

        if (name === 'montar_cb') {
          endTrace(this.threadId, 'montar_callback_return');
        }
      }
    });
    markerHandles.push(h);
    sendEvent('hook_ok', {name:name, rva:'0x'+rva.toString(16).toUpperCase(), address:phex(at)});
  } catch (e) {
    sendEvent('hook_error', {name:name, rva:'0x'+rva.toString(16).toUpperCase(), error:String(e)});
  }
}

function beginTrace(tid, montarEvt) {
  if (active.has(tid)) return;

  const id = ++traceSeq;
  const state = {
    id:id,
    tid:tid,
    started:Date.now(),
    calls:0,
    ams_calls:0,
    external_calls:0
  };
  active.set(tid, state);
  sendEvent('trace_begin', {trace_id:id, thread_id:tid, montar:montarEvt});

  try {
    Stalker.follow(tid, {
      events: {
        call: true,
        ret: false,
        exec: false,
        block: false,
        compile: false
      },
      onReceive(rawEvents) {
        const st = active.get(tid);
        let parsed;
        try {
          parsed = Stalker.parse(rawEvents, {annotate:true, stringify:false});
        } catch (e) {
          sendEvent('stalker_parse_error', {trace_id:id, error:String(e)});
          return;
        }

        const batch = [];
        for (const ev of parsed) {
          if (!Array.isArray(ev) || ev.length < 3) continue;
          if (ev[0] !== 'call') continue;

          const from = safePtr(ev[1]);
          const to = safePtr(ev[2]);
          const depth = ev.length >= 4 ? ev[3] : null;
          state.calls++;

          const fromIn = inAms(from);
          const toIn = inAms(to);
          if (toIn) state.ams_calls++; else state.external_calls++;

          // Keep full AMS path. External calls are kept only if originating in AMS.
          if (!toIn && !fromIn) continue;

          const toRva = rvaOf(to);
          const fromRva = rvaOf(from);
          batch.push({
            from: phex(from),
            from_rva: fromRva === null ? null : '0x'+fromRva.toString(16).toUpperCase(),
            to: phex(to),
            to_rva: toRva === null ? null : '0x'+toRva.toString(16).toUpperCase(),
            to_marker: markerNameFor(to),
            depth: depth
          });

          if (batch.length >= 250) {
            sendEvent('call_batch', {trace_id:id, thread_id:tid, calls:batch.splice(0,batch.length)});
          }
        }
        if (batch.length)
          sendEvent('call_batch', {trace_id:id, thread_id:tid, calls:batch});
      }
    });
  } catch (e) {
    sendEvent('stalker_error', {trace_id:id, error:String(e)});
  }
}

function endTrace(tid, reason) {
  const st = active.get(tid);
  if (!st) return;
  try {
    Stalker.unfollow(tid);
    Stalker.flush();
    Stalker.garbageCollect();
  } catch (_) {}
  active.delete(tid);
  sendEvent('trace_end', {
    trace_id:st.id,
    thread_id:tid,
    reason:reason,
    elapsed_ms:Date.now()-st.started,
    raw_call_count:st.calls,
    ams_call_count:st.ams_calls,
    external_call_count:st.external_calls
  });
}

function hookExport(moduleName, exportName, callbacks) {
  try {
    const m = Process.findModuleByName(moduleName);
    if (m === null) return;
    const p = m.findExportByName(exportName);
    if (p === null) return;
    const h = Interceptor.attach(p, callbacks);
    markerHandles.push(h);
    sendEvent('net_hook_ok', {module:moduleName, export:exportName, address:phex(p)});
  } catch (e) {
    sendEvent('net_hook_error', {module:moduleName, export:exportName, error:String(e)});
  }
}

function installNetworkHooks() {
  const reqA = {
    onEnter(args) {
      sendEvent('network', {
        api:'HttpOpenRequestA',
        verb:safeReadUtf8(args[1],64),
        object:safeReadUtf8(args[2],2048),
        thread_id:this.threadId
      });
    }
  };
  const reqW = {
    onEnter(args) {
      sendEvent('network', {
        api:'HttpOpenRequestW',
        verb:safeReadUtf16(args[1],64),
        object:safeReadUtf16(args[2],2048),
        thread_id:this.threadId
      });
    }
  };
  const sendA = {
    onEnter(args) {
      sendEvent('network', {
        api:'HttpSendRequestA',
        headers:safeReadUtf8(args[1],4096),
        optional_ptr:phex(args[3]),
        optional_len:args[4].toUInt32(),
        thread_id:this.threadId
      });
    }
  };
  const sendW = {
    onEnter(args) {
      sendEvent('network', {
        api:'HttpSendRequestW',
        headers:safeReadUtf16(args[1],4096),
        optional_ptr:phex(args[3]),
        optional_len:args[4].toUInt32(),
        thread_id:this.threadId
      });
    }
  };
  const openUrlA = {
    onEnter(args) {
      sendEvent('network', {
        api:'InternetOpenUrlA',
        url:safeReadUtf8(args[1],4096),
        headers:safeReadUtf8(args[2],4096),
        thread_id:this.threadId
      });
    }
  };
  const openUrlW = {
    onEnter(args) {
      sendEvent('network', {
        api:'InternetOpenUrlW',
        url:safeReadUtf16(args[1],4096),
        headers:safeReadUtf16(args[2],4096),
        thread_id:this.threadId
      });
    }
  };

  hookExport('wininet.dll','HttpOpenRequestA',reqA);
  hookExport('wininet.dll','HttpOpenRequestW',reqW);
  hookExport('wininet.dll','HttpSendRequestA',sendA);
  hookExport('wininet.dll','HttpSendRequestW',sendW);
  hookExport('wininet.dll','InternetOpenUrlA',openUrlA);
  hookExport('wininet.dll','InternetOpenUrlW',openUrlW);
}

function init() {
  mod = Process.getModuleByName('AMS.exe');
  base = mod.base;
  end = base.add(mod.size);

  sendEvent('ready', {
    module:mod.name,
    base:phex(base),
    size:mod.size,
    path:mod.path,
    arch:Process.arch,
    platform:Process.platform
  });

  for (const name of Object.keys(RVAS))
    installMarker(name, RVAS[name]);

  installNetworkHooks();
}

setImmediate(init);
"""

def now_tag():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

def find_process(device, name="AMS.exe"):
    for p in device.enumerate_processes():
        if p.name.lower() == name.lower():
            return p
    return None

def summarize(events):
    summary = {
        "trace_count": 0,
        "markers_seen": {},
        "network_events": [],
        "trace_ends": [],
        "call_edge_count": 0,
        "unique_internal_targets": 0,
        "known_path": [],
    }
    targets = set()
    marker_order = []
    for e in events:
        kind = e.get("kind")
        if kind == "trace_begin":
            summary["trace_count"] += 1
        elif kind == "marker_enter":
            n = e.get("name")
            summary["markers_seen"][n] = summary["markers_seen"].get(n, 0) + 1
            marker_order.append(n)
        elif kind == "network":
            summary["network_events"].append(e)
        elif kind == "trace_end":
            summary["trace_ends"].append(e)
        elif kind == "call_batch":
            calls = e.get("calls") or []
            summary["call_edge_count"] += len(calls)
            for c in calls:
                r = c.get("to_rva")
                if r:
                    targets.add(r)
    summary["unique_internal_targets"] = len(targets)
    summary["known_path"] = marker_order

    if summary["markers_seen"].get("montar_cb",0) == 0:
        summary["diagnosis"] = "MONTAR callback nao foi observado."
    elif summary["markers_seen"].get("signal_invoke",0) == 0:
        summary["diagnosis"] = "Clique entrou no callback, mas nao chegou a SignalInvoke."
    elif summary["markers_seen"].get("build_car",0) == 0:
        summary["diagnosis"] = "SignalInvoke ocorreu, mas GS_Garage::BuildCar nao foi chamado."
    elif summary["markers_seen"].get("craft_caller",0) == 0:
        summary["diagnosis"] = "BuildCar foi chamado, mas CraftCarCaller nao foi alcancado."
    elif summary["markers_seen"].get("craft_wrapper",0) == 0 and summary["markers_seen"].get("craft_body",0) == 0:
        summary["diagnosis"] = "CraftCarCaller foi chamado, mas CraftCar request nao foi criado."
    elif summary["markers_seen"].get("craft_result",0) == 0:
        summary["diagnosis"] = "CraftCar request foi criado, mas resultado nao retornou durante a captura."
    else:
        summary["diagnosis"] = "Fluxo chegou ao resultado CraftCar."

    return summary

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", required=True)
    ap.add_argument("--seconds", type=int, default=180,
                    help="tempo maximo de captura apos anexar")
    ns = ap.parse_args()

    root = Path(ns.project_root).resolve()
    out_dir = root / "_TRACE_MONTAR"
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = now_tag()
    jsonl_path = out_dir / f"MONTAR-TRACE-{tag}.jsonl"
    summary_path = out_dir / f"MONTAR-SUMMARY-{tag}.json"

    print("================================================================")
    print(" ASPHALT ReXTREME - MONTAR DYNAMIC TRACE")
    print("================================================================")
    print()
    print("[1/5] Procurando AMS.exe...")
    device = frida.get_local_device()
    proc = None
    while proc is None:
        proc = find_process(device)
        if proc is None:
            time.sleep(0.5)
    print(f"[2/5] AMS.exe encontrado: PID {proc.pid}")

    try:
        session = device.attach(proc.pid)
    except Exception as e:
        print("[ERRO] Nao consegui anexar ao AMS.exe:", e)
        print("Tente executar este CMD como Administrador.")
        return 3

    events = []
    trace_completed = False
    got_montar = False

    f = jsonl_path.open("w", encoding="utf-8")

    def write_event(evt):
        nonlocal trace_completed, got_montar
        events.append(evt)
        f.write(json.dumps(evt, ensure_ascii=False) + "\n")
        f.flush()

        kind = evt.get("kind")
        if kind == "ready":
            print(f"[3/5] Instrumentacao pronta. Base={evt.get('base')} arch={evt.get('arch')}")
            print()
            print(">>> AGORA clique MONTAR UMA VEZ no jogo. <<<")
            print()
        elif kind == "marker_enter":
            n = evt.get("name")
            if n == "montar_cb":
                got_montar = True
                print(f"[MONTAR] callback thread={evt.get('thread_id')} signal={evt.get('signal')} owner={evt.get('owner')}")
            elif n == "signal_invoke":
                print("[PATH] SignalInvoke")
            elif n == "build_car":
                print("[PATH] GS_Garage::BuildCar")
            elif n == "craft_caller":
                print("[PATH] CraftCarCaller")
            elif n in ("craft_wrapper","craft_body"):
                print(f"[PATH] {n}")
            elif n == "craft_result":
                print("[PATH] CraftCar_Result")
        elif kind == "network":
            print(f"[NET] {evt.get('api')} url/object={evt.get('url') or evt.get('object')}")
        elif kind == "trace_end":
            trace_completed = True
            print(f"[TRACE] terminou: AMS calls={evt.get('ams_call_count')} external={evt.get('external_call_count')}")

    def on_message(message, data):
        if message.get("type") == "send":
            payload = message.get("payload")
            if isinstance(payload, dict):
                write_event(payload)
        elif message.get("type") == "error":
            evt = {"kind":"agent_error","description":message.get("description"),
                   "stack":message.get("stack")}
            write_event(evt)
            print("[AGENT ERRO]", message.get("description"))
        else:
            write_event({"kind":"frida_message","message":message})

    try:
        script = session.create_script(AGENT)
        script.on("message", on_message)
        script.load()
        print("[4/5] Capturando...")

        deadline = time.time() + ns.seconds
        completed_at = None
        while time.time() < deadline:
            if trace_completed and completed_at is None:
                completed_at = time.time()
            if completed_at is not None and time.time() - completed_at >= 2.0:
                break
            time.sleep(0.1)

        summary = summarize(events)
        summary["created_at"] = datetime.datetime.now().isoformat()
        summary["raw_log"] = str(jsonl_path)
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

        print()
        print("[5/5] CAPTURA FINALIZADA")
        print("Diagnostico:", summary["diagnosis"])
        print("Markers:", json.dumps(summary["markers_seen"], ensure_ascii=False))
        print("CALLs registradas:", summary["call_edge_count"])
        print("Targets internos unicos:", summary["unique_internal_targets"])
        print("Network events:", len(summary["network_events"]))
        print()
        print("Arquivos:")
        print(" ", jsonl_path)
        print(" ", summary_path)
        print()
        if not got_montar:
            print("AVISO: MONTAR nao foi observado dentro do tempo de captura.")
        return 0
    except KeyboardInterrupt:
        print("\n[INFO] Captura encerrada pelo usuario.")
        return 0
    except Exception:
        traceback.print_exc()
        return 4
    finally:
        try: f.close()
        except Exception: pass
        try: session.detach()
        except Exception: pass

if __name__ == "__main__":
    raise SystemExit(main())
