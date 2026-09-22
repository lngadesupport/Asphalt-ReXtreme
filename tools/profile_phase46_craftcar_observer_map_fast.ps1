param(
  [Parameter(Mandatory=$true)][string]$ProjectRoot
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=(Resolve-Path -LiteralPath $ProjectRoot).Path
$game=Join-Path $root "_PACKAGE_PHASE5"
$ams=Join-Path $game "AMS.exe"
$outDir=Join-Path $game "_PHASE46_BUILD_OBSERVER_MAP"
$out=Join-Path $outDir "LATEST-PHASE46-BUILD-OBSERVER-MAP.txt"
New-Item -ItemType Directory -Force -Path $outDir|Out-Null

if(-not(Test-Path -LiteralPath $ams -PathType Leaf)){throw "AMS.exe not found"}

$expectedHash="22fe7b0bd9c8c73e79c14efaef4cdc5dd4d4bbcabd17e855db312f0a776851cc"
$hash=(Get-FileHash -LiteralPath $ams -Algorithm SHA256).Hash.ToLowerInvariant()
if($hash-ne$expectedHash){throw ("Expected Phase36-only AMS hash "+$expectedHash+", got "+$hash)}

$src=@"
using System;
using System.IO;
using System.Text;
using System.Collections.Generic;

public static class Phase46Fast {
    class Sec {
        public string Name="";
        public uint VSize, VA, RawSize, Raw, Chars;
    }

    static ushort U16(byte[] d,int o){ return BitConverter.ToUInt16(d,o); }
    static uint U32(byte[] d,int o){ return BitConverter.ToUInt32(d,o); }
    static int I32(byte[] d,int o){ return BitConverter.ToInt32(d,o); }

    static List<Sec> ParsePE(byte[] d, out uint imageBase) {
        int pe=(int)U32(d,0x3C);
        if(d[pe]!=(byte)'P'||d[pe+1]!=(byte)'E'||d[pe+2]!=0||d[pe+3]!=0) throw new Exception("Invalid PE");
        ushort machine=U16(d,pe+4), nsec=U16(d,pe+6), optSize=U16(d,pe+20);
        int opt=pe+24;
        ushort magic=U16(d,opt);
        if(machine!=0x14C||magic!=0x10B) throw new Exception("Expected x86 PE32");
        imageBase=U32(d,opt+28);
        int secOff=opt+optSize;
        var secs=new List<Sec>();
        for(int i=0;i<nsec;i++){
            int o=secOff+i*40;
            string name=Encoding.ASCII.GetString(d,o,8).TrimEnd('\0');
            secs.Add(new Sec{
                Name=name,VSize=U32(d,o+8),VA=U32(d,o+12),
                RawSize=U32(d,o+16),Raw=U32(d,o+20),Chars=U32(d,o+36)
            });
        }
        return secs;
    }

    static long FileToVa(List<Sec> secs,uint imageBase,int off){
        foreach(var s in secs)
            if(off>=s.Raw && off<(long)s.Raw+s.RawSize)
                return (long)imageBase+s.VA+(off-(long)s.Raw);
        return -1;
    }

    static int VaToFile(List<Sec> secs,uint imageBase,uint va){
        long rva=(long)va-imageBase;
        if(rva<0) return -1;
        foreach(var s in secs){
            long span=Math.Max((long)s.VSize,(long)s.RawSize);
            if(rva>=s.VA && rva<(long)s.VA+span)
                return (int)(s.Raw+(rva-s.VA));
        }
        return -1;
    }

    static bool IsExecVa(List<Sec> secs,uint imageBase,uint va){
        long rva=(long)va-imageBase;
        foreach(var s in secs){
            long span=Math.Max((long)s.VSize,(long)s.RawSize);
            if(rva>=s.VA && rva<(long)s.VA+span)
                return (s.Chars & 0x20000000)!=0;
        }
        return false;
    }

    static string HexDump(byte[] d,int start,int before,int after){
        int a=Math.Max(0,start-before), z=Math.Min(d.Length,start+after);
        var sb=new StringBuilder();
        for(int p=a;p<z;p+=16){
            int n=Math.Min(16,z-p);
            sb.AppendFormat("0x{0:X8}: ",p);
            for(int i=0;i<n;i++){ if(i>0) sb.Append(' '); sb.Append(d[p+i].ToString("X2")); }
            sb.AppendLine();
        }
        return sb.ToString();
    }

    static List<int> DwordRefs(byte[] d,uint value){
        byte[] p=BitConverter.GetBytes(value);
        var r=new List<int>();
        for(int i=0;i<=d.Length-4;i++){
            if(d[i]==p[0]&&d[i+1]==p[1]&&d[i+2]==p[2]&&d[i+3]==p[3]) r.Add(i);
        }
        return r;
    }

    public static void Run(string amsPath,string outPath,string hash){
        byte[] d=File.ReadAllBytes(amsPath);
        uint imageBase;
        var secs=ParsePE(d,out imageBase);

        var execRanges=new List<Tuple<int,int>>();
        foreach(var s in secs){
            if((s.Chars&0x20000000)==0) continue;
            int a=(int)s.Raw, z=(int)Math.Min((long)d.Length,(long)s.Raw+s.RawSize);
            execRanges.Add(Tuple.Create(a,z));
        }

        // One-pass index of all direct E8 rel32 calls.
        var callIndex=new Dictionary<uint,List<int>>();
        foreach(var rg in execRanges){
            int i=rg.Item1, end=Math.Max(rg.Item1,rg.Item2-5);
            while(i<=end){
                if(d[i]==0xE8){
                    long src=FileToVa(secs,imageBase,i);
                    if(src>=0){
                        uint dst=(uint)(src+5+I32(d,i+1));
                        List<int> list;
                        if(!callIndex.TryGetValue(dst,out list)){ list=new List<int>(); callIndex[dst]=list; }
                        list.Add(i);
                    }
                    i+=5;
                } else i++;
            }
        }

        uint[] vtables={0x0184F6C0u,0x0184F41Cu};
        string[] labels={"FINAL_OBSERVER_VTABLE","CTOR_TEMP_VTABLE"};

        var sb=new StringBuilder();
        sb.AppendLine(new string('=',60));
        sb.AppendLine(" ReXtreme Phase 46 - CraftCar Observer VTable Map (Fast C#)");
        sb.AppendLine(new string('=',60));
        sb.AppendLine("AMS_SHA256="+hash);
        sb.AppendFormat("ImageBase=0x{0:X8}\n",imageBase);
        int totalCalls=0; foreach(var kv in callIndex) totalCalls+=kv.Value.Count;
        sb.AppendLine("IndexedDirectCalls="+totalCalls);
        sb.AppendLine();

        for(int vi=0;vi<vtables.Length;vi++){
            uint vt=vtables[vi];
            int off=VaToFile(secs,imageBase,vt);
            sb.AppendFormat("===== {0} VA=0x{1:X8} File={2} =====\n",
                labels[vi],vt,off>=0?("0x"+off.ToString("X8")):"N/A");
            if(off<0){ sb.AppendLine(); continue; }

            for(int slot=0;slot<24;slot++){
                int eo=off+slot*4;
                if(eo+4>d.Length) break;
                uint fn=U32(d,eo);
                int fo=VaToFile(secs,imageBase,fn);
                bool exec=IsExecVa(secs,imageBase,fn);
                sb.AppendFormat("slot={0,2} entryFile=0x{1:X8} fnVA=0x{2:X8} fnFile={3} Exec={4}\n",
                    slot,eo,fn,fo>=0?("0x"+fo.ToString("X8")):"N/A",exec);
                if(exec && fo>=0){
                    sb.Append(HexDump(d,fo,0,112));
                    List<int> callers;
                    int cnt=callIndex.TryGetValue(fn,out callers)?callers.Count:0;
                    sb.AppendLine("DirectCallers="+cnt);
                    if(callers!=null){
                        int lim=Math.Min(20,callers.Count);
                        for(int k=0;k<lim;k++){
                            int c=callers[k];
                            long cv=FileToVa(secs,imageBase,c);
                            sb.AppendFormat(" callerFile=0x{0:X8} callerVA=0x{1:X8}\n",c,cv);
                            sb.Append(HexDump(d,c,24,48));
                        }
                    }
                    int hi=Math.Min(d.Length-4,fo+128);
                    for(int p=fo;p<=hi;p++){
                        int v=I32(d,p);
                        if(v==0x298||v==-0x298)
                            sb.AppendFormat("  ** +/-0x298 immediate @ file=0x{0:X8}\n",p);
                    }
                }
                sb.AppendLine();
            }
        }

        sb.AppendLine("===== EXECUTABLE REFS TO FINAL OBSERVER VTABLE =====");
        foreach(int r in DwordRefs(d,0x0184F6C0u)){
            bool ex=false;
            foreach(var rg in execRanges) if(r>=rg.Item1&&r<rg.Item2){ex=true;break;}
            if(!ex) continue;
            long rv=FileToVa(secs,imageBase,r);
            sb.AppendFormat("refFile=0x{0:X8} refVA=0x{1:X8}\n",r,rv);
            sb.Append(HexDump(d,r,48,96)); sb.AppendLine();
        }

        sb.AppendLine("===== BUILD HANDLER REGISTRATION WINDOW =====");
        sb.Append(HexDump(d,0x006870D0,32,176));

        File.WriteAllText(outPath,sb.ToString(),new UTF8Encoding(false));
        Console.WriteLine(new string('=',60));
        Console.WriteLine(" PHASE 46 CRAFTCAR OBSERVER MAP READY (Fast C#)");
        Console.WriteLine(new string('=',60));
        Console.WriteLine("Indexed direct calls: "+totalCalls);
        Console.WriteLine("Report: "+outPath);
    }
}
"@

Add-Type -TypeDefinition $src -Language CSharp
[Phase46Fast]::Run($ams,$out,$hash)
