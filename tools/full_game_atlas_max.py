#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, struct, json, csv, re, time, bisect
from pathlib import Path
from collections import defaultdict, deque, Counter

STABLE_SHA="7f257d1188285a821dda73ce4816757aa23cdc2537e43b8f53c6dc96b9bc39cb"

# Guarded current profile state.
GUARDS=[
    ("Phase53",0x00574FA7,bytes.fromhex("6A 01 90")),
    ("Phase54",0x0059F3F2,bytes.fromhex("B8 02 00 00 00 90")),
    ("Phase55",0x00573C45,bytes.fromhex("90 90 90 90 90 90")),
    ("Phase63Reverted",0x00573CF4,bytes.fromhex("74 0B")),
    ("Phase65Reverted",0x0056E9CE,bytes.fromhex("0F 94 45 E3")),
    ("GlobalIsOnlineFALSE",0x00BACDD0,bytes.fromhex("31 C0 C3 90 90 90 90")),
    ("Phase36Popup",0x009168B0,bytes.fromhex("31 C0 C2 18 00")),
]

KNOWN_ANCHORS={
    "GarageBottomBarWidget_vtable":0x01831854,
    "GarageBottomBarWidget_ctor":0x0096EB10,
    "GarageBottomBarWidget_callback_build":0x00973C90,
    "GarageBottomBarWidget_register_buttons":0x00972B90,
    "GarageBottomBarWidget_template_builder":0x0096F3B0,
    "GS_Garage_vtable":0x0186A9CC,
    "GS_Garage_ctor":0x00E00B20,
    "GS_Garage_build_handler":0x00A87960,
    "CraftCar_caller":0x0099FF50,
    "CraftCar":0x009A4BA0,
    "CraftCar_result":0x009A48A0,
    "RegisterHelper":0x0096E4B0,
    "SignalInvokeHelper":0x00936BE0,
    "GlobalIsOnline":0x00FAD9D0, # code VA derived from file 0x00BACDD0 + image mapping; retained as known anchor label only
}

NETWORK_KEYWORDS=(
    "http://","https://",".php","gameloft","server","online","offline","network",
    "connection","connect","timeout","request","response","endpoint","api/","scripts/"
)
GAMEPLAY_KEYWORDS=(
    "garage","craft","car","upgrade","race","reward","profile","save","blueprint",
    "mission","career","inventory","currency","coin","token","fuel","build_button",
    "ready_to_build","bottom_bar","tutorial"
)
RTTI_PREFIX=b".?AV"

REGS=["eax","ecx","edx","ebx","esp","ebp","esi","edi"]

def u16(b,o): return struct.unpack_from("<H",b,o)[0]
def u32(b,o): return struct.unpack_from("<I",b,o)[0]
def i8v(x): return x-256 if x>=128 else x
def i32(b,o): return struct.unpack_from("<i",b,o)[0]
def sha256_bytes(b): return hashlib.sha256(b).hexdigest()

def parse_pe(d):
    pe=u32(d,0x3c)
    if d[pe:pe+4]!=b"PE\0\0": raise RuntimeError("invalid PE")
    machine=u16(d,pe+4); n=u16(d,pe+6); optsz=u16(d,pe+20); opt=pe+24
    magic=u16(d,opt)
    if machine!=0x14c or magic!=0x10b: raise RuntimeError("expected x86 PE32")
    entry_rva=u32(d,opt+16)
    image_base=u32(d,opt+28)
    num_dirs=u32(d,opt+92)
    dirs=[]
    dd=opt+96
    for i in range(min(num_dirs,16)):
        dirs.append((u32(d,dd+i*8),u32(d,dd+i*8+4)))
    so=opt+optsz
    secs=[]
    for i in range(n):
        o=so+i*40
        secs.append({
            "name":d[o:o+8].split(b"\0",1)[0].decode("ascii","replace"),
            "vs":u32(d,o+8),"va":u32(d,o+12),"rs":u32(d,o+16),
            "raw":u32(d,o+20),"ch":u32(d,o+36)
        })
    return {
        "pe":pe,"image_base":image_base,"entry_va":image_base+entry_rva,
        "sections":secs,"dirs":dirs
    }

def f2v(off,pe):
    ib=pe["image_base"]
    for s in pe["sections"]:
        if s["raw"]<=off<s["raw"]+s["rs"]:
            return ib+s["va"]+(off-s["raw"])
    return None

def v2f(va,pe):
    rva=va-pe["image_base"]
    for s in pe["sections"]:
        if s["va"]<=rva<s["va"]+max(s["vs"],s["rs"]):
            return s["raw"]+(rva-s["va"])
    return None

def executable_sections(pe):
    return [s for s in pe["sections"] if s["ch"] & 0x20000000]

def readable_sections(pe):
    return [s for s in pe["sections"] if s["ch"] & 0x40000000]

def is_exec_va(va,pe):
    f=v2f(va,pe)
    if f is None:return False
    return any(s["raw"]<=f<s["raw"]+s["rs"] for s in executable_sections(pe))

def section_name_for_file(off,pe):
    for s in pe["sections"]:
        if s["raw"]<=off<s["raw"]+s["rs"]: return s["name"]
    return ""

def rva_to_file(rva,pe):
    return v2f(pe["image_base"]+rva,pe)

def c_string(d,off,limit=4096):
    z=d.find(b"\0",off,min(len(d),off+limit))
    if z<0:z=min(len(d),off+limit)
    return d[off:z]

def build_prologue_index(d,pe):
    starts=set()
    # Common MSVC x86 prologues + naked/optimized entry targets added later.
    patterns=(b"\x55\x8B\xEC", b"\x53\x56\x57", b"\x56\x8B\xF1", b"\x57\x8B\xF9")
    for s in executable_sections(pe):
        a=s["raw"]; b=min(len(d),a+s["rs"])
        # Conservative primary prologue only; other patterns are not standalone function proof.
        pos=a
        while True:
            p=d.find(b"\x55\x8B\xEC",pos,b)
            if p<0:break
            starts.add(p);pos=p+3
    return starts

def scan_direct_transfers(d,pe):
    calls=[]
    jumps=[]
    targets=set()
    for s in executable_sections(pe):
        a=s["raw"]; b=min(len(d),a+s["rs"])
        p=a
        while p<b:
            op=d[p]
            sva=f2v(p,pe)
            if sva is None:
                p+=1;continue
            if op==0xE8 and p+5<=b:
                dst=(sva+5+i32(d,p+1))&0xffffffff
                if is_exec_va(dst,pe):
                    calls.append((p,sva,dst))
                    targets.add(v2f(dst,pe))
                p+=5;continue
            if op==0xE9 and p+5<=b:
                dst=(sva+5+i32(d,p+1))&0xffffffff
                if is_exec_va(dst,pe):
                    jumps.append((p,sva,dst,"JMP32"))
                    targets.add(v2f(dst,pe))
                p+=5;continue
            if op==0xEB and p+2<=b:
                dst=(sva+2+i8v(d[p+1]))&0xffffffff
                if is_exec_va(dst,pe):
                    jumps.append((p,sva,dst,"JMP8"))
                p+=2;continue
            p+=1
    return calls,jumps,{x for x in targets if x is not None}

def build_function_ranges(d,pe,prologue_starts,call_targets,jump_targets):
    starts=set(prologue_starts)
    starts.update(call_targets)
    starts.update(jump_targets)
    ep=v2f(pe["entry_va"],pe)
    if ep is not None:starts.add(ep)
    starts={x for x in starts if x is not None and any(s["raw"]<=x<s["raw"]+s["rs"] for s in executable_sections(pe))}
    ordered=sorted(starts)
    funcs=[]
    for s in executable_sections(pe):
        local=[x for x in ordered if s["raw"]<=x<s["raw"]+s["rs"]]
        for i,fs in enumerate(local):
            fe=local[i+1] if i+1<len(local) else s["raw"]+s["rs"]
            # cap absurd overlap gaps caused by sparse targets, but keep complete section coverage mapping.
            funcs.append((fs,fe,f2v(fs,pe),section_name_for_file(fs,pe)))
    funcs.sort()
    return funcs

def make_function_index(funcs):
    return [x[0] for x in funcs]

def function_for_file(off,funcs,starts=None):
    if starts is None:
        starts=make_function_index(funcs)
    i=bisect.bisect_right(starts,off)-1
    if i<0:return None
    fs,fe,va,sec=funcs[i]
    if fs<=off<fe:return (fs,fe,va,sec)
    return None

def build_call_graph(calls,funcs,func_starts):
    edges=[]
    callers=defaultdict(list); callees=defaultdict(list)
    total=len(calls)
    for idx,(file_off,call_va,dst_va) in enumerate(calls,1):
        src=function_for_file(file_off,funcs,func_starts)
        edges.append((src[2] if src else None,dst_va,file_off,call_va))
        if src:
            callees[src[2]].append((dst_va,file_off))
            callers[dst_va].append((src[2],file_off))
        if idx%100000==0 or idx==total:
            print(f"         call graph {idx}/{total}",flush=True)
    return edges,callers,callees

def extract_ascii_strings(d,pe,min_len=4):
    out=[]
    for s in readable_sections(pe):
        a=s["raw"];b=min(len(d),a+s["rs"])
        i=a
        while i<b:
            if 32<=d[i]<=126:
                j=i
                while j<b and 32<=d[j]<=126:j+=1
                if j-i>=min_len:
                    raw=d[i:j]
                    try:txt=raw.decode("ascii")
                    except:txt=""
                    if txt:out.append((i,f2v(i,pe),s["name"],txt))
                i=max(j+1,i+1)
            else:i+=1
    return out

def extract_utf16_strings(d,pe,min_chars=4):
    out=[]
    for s in readable_sections(pe):
        a=s["raw"];b=min(len(d),a+s["rs"])
        i=a
        while i+2<=b:
            j=i;chars=[]
            while j+2<=b:
                c=u16(d,j)
                if 32<=c<=126:
                    chars.append(chr(c));j+=2
                else:break
            if len(chars)>=min_chars:
                out.append((i,f2v(i,pe),s["name"],"".join(chars)))
                i=j+2
            else:i+=2
    return out

def build_immediate_xrefs(d,pe,values,funcs,func_starts):
    # MAX optimized: one linear pass over executable bytes instead of one full scan per string.
    wanted={v for v in values if v is not None and 0<=v<=0xffffffff}
    xrefs=defaultdict(list)
    if not wanted:return xrefs
    total_bytes=sum(s["rs"] for s in executable_sections(pe))
    done=0
    for s in executable_sections(pe):
        a=s["raw"];b=min(len(d),a+s["rs"])
        # Any imm32/pointer can start at an unaligned byte.
        p=a
        stop=max(a,b-3)
        while p<stop:
            v=struct.unpack_from("<I",d,p)[0]
            if v in wanted:
                fn=function_for_file(p,funcs,func_starts)
                xrefs[v].append((p,f2v(p,pe),fn[2] if fn else None))
            p+=1
        done+=b-a
        print(f"         xref scan bytes {done}/{total_bytes}",flush=True)
    return xrefs

def parse_imports(d,pe):
    out=[]
    if len(pe["dirs"])<2:return out
    rva,size=pe["dirs"][1]
    off=rva_to_file(rva,pe)
    if off is None:return out
    p=off
    while p+20<=len(d):
        oft=u32(d,p); tds=u32(d,p+4); fwd=u32(d,p+8); name_rva=u32(d,p+12); ft=u32(d,p+16)
        if not any((oft,tds,fwd,name_rva,ft)):break
        no=rva_to_file(name_rva,pe)
        dll=c_string(d,no).decode("ascii","replace") if no is not None else "?"
        thunk_rva=oft or ft
        to=rva_to_file(thunk_rva,pe)
        if to is not None:
            q=to;idx=0
            while q+4<=len(d):
                ent=u32(d,q)
                if ent==0:break
                if ent&0x80000000:
                    name=f"ordinal_{ent&0xffff}"
                else:
                    hn=rva_to_file(ent,pe)
                    if hn is not None and hn+2<len(d):
                        name=c_string(d,hn+2).decode("ascii","replace")
                    else:name="?"
                iat_va=pe["image_base"]+ft+idx*4
                out.append((dll,name,iat_va))
                q+=4;idx+=1
        p+=20
    return out

def extract_rtti_names(d,pe):
    out=[]
    pos=0
    while True:
        p=d.find(RTTI_PREFIX,pos)
        if p<0:break
        z=d.find(b"\0",p,min(len(d),p+512))
        if z<0: z=min(len(d),p+512)
        raw=d[p:z]
        if 4<=len(raw)<=500:
            try:txt=raw.decode("ascii")
            except:txt=""
            if txt:out.append((p,f2v(p,pe),txt))
        pos=p+4
    return out

def detect_vtables(d,pe,func_starts_va,min_entries=3,max_entries=512):
    funcset=set(func_starts_va)
    out=[]
    # scan non-exec readable sections for runs of executable pointers
    for s in readable_sections(pe):
        if s["ch"]&0x20000000:continue
        a=s["raw"];b=min(len(d),a+s["rs"])
        p=(a+3)&~3
        while p+4<=b:
            va=u32(d,p)
            if is_exec_va(va,pe):
                start=p;vals=[]
                q=p
                while q+4<=b and len(vals)<max_entries:
                    x=u32(d,q)
                    if not is_exec_va(x,pe):break
                    vals.append(x);q+=4
                if len(vals)>=min_entries:
                    out.append((start,f2v(start,pe),s["name"],vals))
                    p=q;continue
            p+=4
    return out

def classify_string(txt):
    lo=txt.lower()
    cats=[]
    if any(k in lo for k in NETWORK_KEYWORDS):cats.append("network")
    if any(k in lo for k in GAMEPLAY_KEYWORDS):cats.append("gameplay")
    if lo.startswith(".?av"):cats.append("rtti")
    if ".php" in lo or "scripts/" in lo:cats.append("endpoint")
    return ",".join(cats) if cats else ""

def write_csv(path,header,rows):
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.writer(f);w.writerow(header);w.writerows(rows)

def bfs_from_roots(roots,callees,max_nodes=1000000):
    seen=set();q=deque((r,0) for r in roots if r is not None);depths={}
    while q and len(seen)<max_nodes:
        va,dep=q.popleft()
        if va in seen:continue
        seen.add(va);depths[va]=dep
        for dst,_ in callees.get(va,()):
            if dst not in seen:q.append((dst,dep+1))
    return seen,depths


def file_sha256(path,chunk=1024*1024):
    h=hashlib.sha256()
    with path.open("rb") as fp:
        while True:
            b=fp.read(chunk)
            if not b:break
            h.update(b)
    return h.hexdigest()

def scan_package_tree(package_root,outdir):
    file_rows=[]
    endpoint_rows=[]
    text_rows=[]
    files=[p for p in package_root.rglob("*") if p.is_file() and outdir not in p.parents]
    total=len(files)
    url_re=re.compile(rb"https?://[^\x00-\x20\"'<>]{4,512}",re.I)
    php_re=re.compile(rb"[A-Za-z0-9_./-]{1,240}\.php(?:\?[A-Za-z0-9_=&%./:+-]{0,240})?",re.I)
    script_re=re.compile(rb"(?:scripts|api)/[A-Za-z0-9_./-]{2,300}",re.I)
    text_exts={".txt",".json",".xml",".csv",".ini",".cfg",".conf",".manifest",".appxmanifest",".html",".htm",".js",".lua",".py",".md",".yaml",".yml"}
    for idx,p in enumerate(files,1):
        try:
            st=p.stat()
            rel=str(p.relative_to(package_root)).replace("\\","/")
            digest=file_sha256(p)
            ext=p.suffix.lower()
            file_rows.append([rel,ext,st.st_size,digest])
            data=None
            # Scan likely-text files fully and binary files up to 64 MiB for endpoint/path strings.
            if ext in text_exts or st.st_size<=64*1024*1024:
                data=p.read_bytes()
                seen=set()
                for kind,rx in (("url",url_re),("php",php_re),("script_path",script_re)):
                    for m in rx.finditer(data):
                        raw=m.group(0)
                        try:txt=raw.decode("utf-8","replace")
                        except:continue
                        key=(kind,txt)
                        if key in seen:continue
                        seen.add(key)
                        endpoint_rows.append([rel,kind,m.start(),txt])
                if ext in text_exts and st.st_size<=16*1024*1024:
                    try:txt=data.decode("utf-8")
                    except:
                        try:txt=data.decode("utf-16")
                        except:txt=""
                    if txt:
                        for ln,line in enumerate(txt.splitlines(),1):
                            lo=line.lower()
                            if any(k in lo for k in NETWORK_KEYWORDS) or any(k in lo for k in GAMEPLAY_KEYWORDS):
                                text_rows.append([rel,ln,line[:2000]])
        except Exception as e:
            file_rows.append([str(p),p.suffix.lower(),"ERROR",repr(e)])
        if idx%250==0 or idx==total:
            print(f"         package files {idx}/{total}",flush=True)
    write_csv(outdir/"PACKAGE_FILES.csv",["relative_path","extension","size","sha256"],file_rows)
    write_csv(outdir/"PACKAGE_ENDPOINT_REFS.csv",["relative_path","kind","byte_offset","text"],endpoint_rows)
    write_csv(outdir/"PACKAGE_RELEVANT_TEXT.csv",["relative_path","line","text"],text_rows)
    return len(file_rows),len(endpoint_rows),len(text_rows)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",required=True)
    ap.add_argument("--dump-bodies",action="store_true",help="write a full hex body dump for every indexed function")
    ns=ap.parse_args()
    root=Path(ns.project_root).resolve()
    ams=root/"_PACKAGE_PHASE5"/"AMS.exe"
    if not ams.is_file():raise SystemExit(f"AMS.exe not found: {ams}")
    d=ams.read_bytes()

    print("[01/15] Verificando SHA/guards...",flush=True)
    for n,o,e in GUARDS:
        if d[o:o+len(e)]!=e:raise SystemExit(f"{n} guard failed at 0x{o:08X}")
    cursha=sha256_bytes(d)
    if cursha!=STABLE_SHA:raise SystemExit(f"Unexpected AMS SHA256 {cursha}; expected {STABLE_SHA}")

    pe=parse_pe(d)
    outdir=root/"_PACKAGE_PHASE5"/"_FULL_GAME_ATLAS_MAX"
    outdir.mkdir(parents=True,exist_ok=True)

    print("[02/15] Indexando prologos...",flush=True)
    prologues=build_prologue_index(d,pe)
    print(f"         prologos primarios={len(prologues)}",flush=True)

    print("[03/15] Varredura global CALL/JMP...",flush=True)
    calls,jumps,targets=scan_direct_transfers(d,pe)
    call_targets={v2f(x[2],pe) for x in calls}
    call_targets={x for x in call_targets if x is not None}
    jump_targets={v2f(x[2],pe) for x in jumps}
    jump_targets={x for x in jump_targets if x is not None}
    print(f"         calls={len(calls)} jumps={len(jumps)} uniqueTargets={len(targets)}",flush=True)

    print("[04/15] Construindo mapa de funcoes (prologos + call/jump targets)...",flush=True)
    funcs=build_function_ranges(d,pe,prologues,call_targets,jump_targets)
    func_starts=make_function_index(funcs)
    print(f"         function starts={len(funcs)}",flush=True)

    print("[05/15] Construindo call graph completo (indexado)...",flush=True)
    edges,callers,callees=build_call_graph(calls,funcs,func_starts)
    print(f"         call edges={len(edges)}",flush=True)

    print("[06/15] Imports...",flush=True)
    imports=parse_imports(d,pe)
    print(f"         imports={len(imports)}",flush=True)

    print("[07/15] Strings ASCII...",flush=True)
    astr=extract_ascii_strings(d,pe,4)
    print(f"         ascii strings={len(astr)}",flush=True)

    print("[08/15] Strings UTF-16...",flush=True)
    wstr=extract_utf16_strings(d,pe,4)
    print(f"         utf16 strings={len(wstr)}",flush=True)

    print("[09/15] RTTI...",flush=True)
    rtti=extract_rtti_names(d,pe)
    print(f"         RTTI names={len(rtti)}",flush=True)

    print("[10/15] Vtables candidatas...",flush=True)
    func_vas=[x[2] for x in funcs]
    vtables=detect_vtables(d,pe,func_vas,3,512)
    print(f"         vtable runs={len(vtables)}",flush=True)

    print("[11/15] XREFs de strings relevantes...",flush=True)
    interesting=[]
    for row in astr+wstr:
        cat=classify_string(row[3])
        if cat:interesting.append((row,cat))
    interesting=interesting[:20000]
    string_xrefs=build_immediate_xrefs(d,pe,[x[0][1] for x in interesting],funcs,func_starts)
    print(f"         relevant strings={len(interesting)}",flush=True)

    print("[12/15] Reachability sem limite pequeno...",flush=True)
    global_roots=[x[2] for x in funcs]
    # all functions are already global; additionally compute subsystem reachability from known anchors.
    garage_roots=[KNOWN_ANCHORS.get("GS_Garage_ctor"),KNOWN_ANCHORS.get("GS_Garage_build_handler"),KNOWN_ANCHORS.get("GarageBottomBarWidget_ctor")]
    garage_seen,garage_depth=bfs_from_roots(garage_roots,callees,1000000)
    craft_roots=[KNOWN_ANCHORS.get("CraftCar"),KNOWN_ANCHORS.get("CraftCar_caller")]
    craft_seen,craft_depth=bfs_from_roots(craft_roots,callees,1000000)
    print(f"         garageReach={len(garage_seen)} craftReach={len(craft_seen)}",flush=True)

    print("[13/15] Mapeando pacote inteiro (_PACKAGE_PHASE5)...",flush=True)
    package_count,package_endpoint_count,package_text_count=scan_package_tree(root/"_PACKAGE_PHASE5",outdir)
    print(f"         packageFiles={package_count} endpointRefs={package_endpoint_count} relevantText={package_text_count}",flush=True)

    print("[14/15] Gravando atlas...",flush=True)
    # FUNCTIONS.csv
    frows=[]
    for fs,fe,va,sec in funcs:
        size=max(0,fe-fs)
        body=d[fs:fe]
        frows.append([
            f"0x{va:08X}",f"0x{fs:08X}",f"0x{fe:08X}",size,sec,
            sha256_bytes(body),len(callers.get(va,())),len(callees.get(va,())),
            1 if va in garage_seen else 0, garage_depth.get(va,""),
            1 if va in craft_seen else 0, craft_depth.get(va,"")
        ])
    write_csv(outdir/"FUNCTIONS.csv",
              ["va","file_start","file_end","size","section","sha256","caller_count","callee_count","garage_reachable","garage_depth","craft_reachable","craft_depth"],
              frows)

    write_csv(outdir/"CALL_GRAPH.csv",
              ["src_function_va","dst_va","call_file","call_va"],
              [[f"0x{x[0]:08X}" if x[0] else "",f"0x{x[1]:08X}",f"0x{x[2]:08X}",f"0x{x[3]:08X}"] for x in edges])

    write_csv(outdir/"JUMP_GRAPH.csv",
              ["jump_file","jump_va","dst_va","kind"],
              [[f"0x{x[0]:08X}",f"0x{x[1]:08X}",f"0x{x[2]:08X}",x[3]] for x in jumps])

    write_csv(outdir/"IMPORTS.csv",["dll","name","iat_va"],
              [[x[0],x[1],f"0x{x[2]:08X}"] for x in imports])

    srows=[]
    for kind,rows in (("ascii",astr),("utf16",wstr)):
        for off,va,sec,txt in rows:
            srows.append([kind,f"0x{off:08X}",f"0x{va:08X}" if va else "",sec,classify_string(txt),txt])
    write_csv(outdir/"STRINGS.csv",["encoding","file","va","section","category","text"],srows)

    xr=[]
    for (row,cat) in interesting:
        off,va,sec,txt=row
        for p,pva,fn in string_xrefs.get(va,()):
            xr.append([cat,txt,f"0x{va:08X}",f"0x{p:08X}",f"0x{pva:08X}",f"0x{fn:08X}" if fn else ""])
    write_csv(outdir/"STRING_XREFS.csv",["category","string","string_va","xref_file","xref_va","function_va"],xr)

    write_csv(outdir/"RTTI.csv",["file","va","name"],
              [[f"0x{x[0]:08X}",f"0x{x[1]:08X}" if x[1] else "",x[2]] for x in rtti])

    vtrows=[]
    for off,va,sec,vals in vtables:
        for idx,x in enumerate(vals):
            vtrows.append([f"0x{va:08X}" if va else "",f"0x{off:08X}",sec,idx,f"0x{idx*4:X}",f"0x{x:08X}"])
    write_csv(outdir/"VTABLES.csv",["vtable_va","vtable_file","section","index","slot","target_va"],vtrows)

    endpoints=[]
    network=[]
    gameplay=[]
    for kind,rows in (("ascii",astr),("utf16",wstr)):
        for off,va,sec,txt in rows:
            cat=classify_string(txt)
            if "endpoint" in cat:endpoints.append([kind,f"0x{off:08X}",f"0x{va:08X}" if va else "",txt])
            if "network" in cat:network.append([kind,f"0x{off:08X}",f"0x{va:08X}" if va else "",txt])
            if "gameplay" in cat:gameplay.append([kind,f"0x{off:08X}",f"0x{va:08X}" if va else "",txt])
    write_csv(outdir/"ENDPOINT_STRINGS.csv",["encoding","file","va","text"],endpoints)
    write_csv(outdir/"NETWORK_STRINGS.csv",["encoding","file","va","text"],network)
    write_csv(outdir/"GAMEPLAY_STRINGS.csv",["encoding","file","va","text"],gameplay)

    anchors={}
    for name,va in KNOWN_ANCHORS.items():
        f=v2f(va,pe)
        fn=function_for_file(f,funcs,func_starts) if f is not None else None
        anchors[name]={
            "va":f"0x{va:08X}",
            "file":f"0x{f:08X}" if f is not None else None,
            "function_va":f"0x{fn[2]:08X}" if fn else None,
            "caller_count":len(callers.get(va,())),
            "callee_count":len(callees.get(va,()))
        }
    (outdir/"KNOWN_ANCHORS.json").write_text(json.dumps(anchors,indent=2),encoding="utf-8")

    # Human-readable index.
    with (outdir/"ATLAS-SUMMARY.txt").open("w",encoding="utf-8") as f:
        f.write("ReXtreme FULL GAME ATLAS MAX\n")
        f.write("="*100+"\n")
        f.write(f"AMS_SHA256={cursha}\n")
        f.write("NO GAMEPLAY BYTES CHANGED\nGlobalIsOnline=FALSE\n\n")
        f.write(f"Functions={len(funcs)}\nDirectCalls={len(calls)}\nDirectJumps={len(jumps)}\n")
        f.write(f"Imports={len(imports)}\nASCIIStrings={len(astr)}\nUTF16Strings={len(wstr)}\n")
        f.write(f"RTTINames={len(rtti)}\nVtableRuns={len(vtables)}\n")
        f.write(f"RelevantStringXrefs={len(xr)}\nEndpoints={len(endpoints)}\nNetworkStrings={len(network)}\nGameplayStrings={len(gameplay)}\n")
        f.write(f"GarageReachability={len(garage_seen)}\nCraftReachability={len(craft_seen)}\n\n")
        f.write("Known anchors:\n")
        for k,v in anchors.items():
            f.write(f"  {k}: {v['va']} file={v['file']} callers={v['caller_count']} callees={v['callee_count']}\n")

    summary={
        "phase":"FULL-GAME-ATLAS-MAX",
        "ams_sha256":cursha,
        "image_base":f"0x{pe['image_base']:08X}",
        "entry_va":f"0x{pe['entry_va']:08X}",
        "function_count":len(funcs),
        "mapping_engine":"indexed-binary-search + single-pass string-xrefs",
        "direct_call_count":len(calls),
        "direct_jump_count":len(jumps),
        "import_count":len(imports),
        "ascii_string_count":len(astr),
        "utf16_string_count":len(wstr),
        "rtti_name_count":len(rtti),
        "vtable_run_count":len(vtables),
        "relevant_string_xref_count":len(xr),
        "endpoint_string_count":len(endpoints),
        "network_string_count":len(network),
        "gameplay_string_count":len(gameplay),
        "package_file_count":package_count,
        "package_endpoint_ref_count":package_endpoint_count,
        "package_relevant_text_count":package_text_count,
        "garage_reachable_functions":len(garage_seen),
        "craft_reachable_functions":len(craft_seen),
        "known_anchors":anchors,
        "outputs":[
            "ATLAS-SUMMARY.txt","SUMMARY.json","FUNCTIONS.csv","CALL_GRAPH.csv","JUMP_GRAPH.csv",
            "IMPORTS.csv","STRINGS.csv","STRING_XREFS.csv","RTTI.csv","VTABLES.csv",
            "ENDPOINT_STRINGS.csv","NETWORK_STRINGS.csv","GAMEPLAY_STRINGS.csv","KNOWN_ANCHORS.json",
            "PACKAGE_FILES.csv","PACKAGE_ENDPOINT_REFS.csv","PACKAGE_RELEVANT_TEXT.csv"
        ],
        "no_gameplay_bytes_changed":True,
        "global_isonline":"FALSE"
    }
    (outdir/"SUMMARY.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")

    if ns.dump_bodies:
        print("         Dumping ALL indexed function bodies (can be very large)...",flush=True)
        with (outdir/"FUNCTION_BODIES_HEX.txt").open("w",encoding="ascii") as f:
            for idx,(fs,fe,va,sec) in enumerate(funcs,1):
                f.write(f"===== {idx}/{len(funcs)} VA=0x{va:08X} FILE=0x{fs:08X}..0x{fe:08X} SIZE={fe-fs} SECTION={sec} =====\n")
                body=d[fs:fe]
                for p in range(0,len(body),16):
                    chunk=body[p:p+16]
                    f.write(f"0x{fs+p:08X}: "+" ".join(f"{x:02X}" for x in chunk)+"\n")
                f.write("\n")
                if idx%5000==0:print(f"         bodies {idx}/{len(funcs)}",flush=True)

    print("[15/15] FULL GAME ATLAS MAX OK",flush=True)
    print("Output:",outdir,flush=True)
    print("Functions:",len(funcs),flush=True)
    print("Direct calls:",len(calls),flush=True)
    print("RTTI:",len(rtti),flush=True)
    print("Vtables:",len(vtables),flush=True)
    print("Endpoints:",len(endpoints),flush=True)
    print("No gameplay bytes were changed.",flush=True)

if __name__=="__main__":
    main()
