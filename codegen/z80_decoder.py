#-------------------------------------------------------------------------------
#   z80_decoder.py
#   Generate huge switch/case Z80 instruction decoder.
#   See: 
#       http://www.z80.info/decoding.htm
#       http://www.righto.com/2014/10/how-z80s-registers-are-implemented-down.html
#       http://www.z80.info/zip/z80-documented.pdf
#       https://www.omnimaga.org/asm-language/bit-n-(hl)-flags/5/?wap2
#
#   FIXME: long sequences of prefixes 0xDD/0xFD are currently handled wrong!
#-------------------------------------------------------------------------------
import sys

# tab-width for generated code
TabWidth = 2

# the output path
OutPath = '../chips/_z80_decoder.h'

# the target file handle
Out = None

# 8-bit register table, the 'HL' entry is for instructions that use
# (HL), (IX+d) and (IY+d)
r = [ 'B', 'C', 'D', 'E', 'H', 'L', 'HL', 'A' ]

# 16-bit register table, with SP
rp = [ 'BC', 'DE', 'HL', 'SP' ]

# 16-bit register table, with AF (only used for PUSH/POP)
rp2 = [ 'BC', 'DE', 'HL', 'FA' ]

# condition-code table (for conditional jumps etc)
cond = [
    '!(c.F&Z80_ZF)',  # NZ
    '(c.F&Z80_ZF)',   # Z
    '!(c.F&Z80_CF)',   # NC
    '(c.F&Z80_CF)',    # C
    '!(c.F&Z80_PF)',   # PO
    '(c.F&Z80_PF)',    # PE
    '!(c.F&Z80_SF)',   # P
    '(c.F&Z80_SF)'     # M
]

# the same as 'human readable' flags for comments
cond_cmt = [ 'NZ', 'Z', 'NC', 'C', 'PO', 'PE', 'P', 'M' ]

# 8-bit ALU instructions command names
alu_cmt = [ 'ADD', 'ADC', 'SUB', 'SBC', 'AND', 'XOR', 'OR', 'CP' ]

# rot and shift instruction command names
rot_cmt = [ 'RLC', 'RRC', 'RL', 'RR', 'SLA', 'SRA', 'SLL', 'SRL' ]

# an 'opcode' wraps the instruction byte, human-readable asm mnemonics,
# and the source code which implements the instruction
class opcode :
    def __init__(self, op) :
        self.byte = op
        self.cmt = None
        self.src = None

indent = 0

#-------------------------------------------------------------------------------
#   output a src line
#
def l(s) :
    Out.write(tab()+s+'\n')

#-------------------------------------------------------------------------------
#   Generate code for one or more 'ticks', call tick callback and increment 
#   the ticks counter.
#
def tick(num=1):
    return '_T('+str(num)+');'

#-------------------------------------------------------------------------------
# instruction fetch machine cycle (M1):
#              T1   T2   T3   T4
#    --------+----+----+----+----+
#    CLK     |--**|--**|--**|--**|
#    A15-A0  |   PC    | REFRESH |
#    MREQ    |   *|****|  **|**  |
#    RD      |   *|****|    |    |
#    WAIT    |    | -- |    |    |
#    M1      |****|****|    |    |
#    D7-D0   |    |   X|    |    |
#    RFSH    |    |    |****|****|
#
# memory-read machine cycle:
#              T1   T2   T3
#    --------+----+----+----+
#    CLK     |--**|--**|--**|
#    A15-A0  |   MEM ADDR   |
#    MREQ    |   *|****|**  |
#    RD      |   *|****|**  |
#    WR      |    |    |    |
#    D7-D0   |    |    | X  |
#    WAIT    |    | -- |    |
#
# memory-write machine cycle:
#              T1   T2   T3
#    --------+----+----+----+
#    CLK     |--**|--**|--**|
#    A15-A0  |   MEM ADDR   |
#    MREQ    |   *|****|**  |
#    RD      |    |    |    |
#    WR      |    |  **|**  |
#    D7-D0   |   X|XXXX|XXXX|
#    WAIT    |    | -- |    |
#
# input machine cycle:
#              T1   T2   TW   T3
#    --------+----+----+----+----+
#    CLK     |--**|--**|--**|--**|
#    A15-A0  |     PORT ADDR     |
#    IORQ    |    |****|****|**  |
#    RD      |    |****|****|**  |
#    WR      |    |    |    |    |
#    D7-D0   |    |    |    | X  |
#    WAIT    |    |    | -- |    |
#
#   NOTE: the implementation moves the activation of the IORQ|RD
#   pins from T2 to TW, so that the pins will only be active 
#   for one tick (assuming no wait states)
#
# output machine cycle:
#              T1   T2   TW   T3
#    --------+----+----+----+----+
#    CLK     |--**|--**|--**|--**|
#    A15-A0  |     PORT ADDR     |
#    IORQ    |    |****|****|**  |
#    RD      |    |    |    |    |
#    WR      |    |****|****|**  |
#    D7-D0   |  XX|XXXX|XXXX|XXXX|
#    WAIT    |    |    | -- |    |
#
#    NOTE: the IORQ|WR pins will already be switched off at the beginning
#    of TW, so that IO devices don't need to do double work.
#

#-------------------------------------------------------------------------------
# write source header
#
def write_header() :
    l('uint32_t z80_exec(z80_t* cpu, uint32_t num_ticks) {')
    l('  uint64_t r0 = cpu->bc_de_hl_fa;')
    l('  uint64_t r1 = cpu->wz_ix_iy_sp;')
    l('  uint64_t r2 = cpu->im_ir_pc_bits;')
    l('  uint64_t r3 = cpu->bc_de_hl_fa_;')
    l('  uint64_t ws = _z80_map_regs(r0, r1, r2);')
    l('  uint64_t map_bits = r2 & _BITS_MAP_REGS;')
    l('  uint64_t pins = cpu->pins;')
    l('  const uint64_t trap_addr = cpu->trap_addr;')
    l('  const z80_tick_t tick = cpu->tick;')
    l('  void* ud = cpu->user_data;')
    l('  int trap_id = -1;')
    l('  uint32_t ticks = 0;')
    l('  uint8_t op, d8;')
    l('  uint16_t addr, d16;')
    l('  uint16_t pc = _G_PC();')
    l('  do {')
    l('    _OFF(Z80_INT);')
    l('    /* delay-enable interrupt flags */')
    l('    if (r2 & _BIT_EI) {')
    l('      r2 &= ~_BIT_EI;')
    l('      r2 |= (_BIT_IFF1 | _BIT_IFF2);')
    l('    }')
    l('    _FETCH(op)')
    l('    if (op == 0xED) {')
    l('      map_bits &= ~(_BIT_USE_IX|_BIT_USE_IY);')
    l('    }')
    l('    if (map_bits != (r2 & _BITS_MAP_REGS)) {')
    l('      const uint64_t old_map_bits = r2 & _BITS_MAP_REGS;')
    l('      r0 = _z80_flush_r0(ws, r0, old_map_bits);')
    l('      r1 = _z80_flush_r1(ws, r1, old_map_bits);')
    l('      r2 = (r2 & ~_BITS_MAP_REGS) | map_bits;')
    l('      ws = _z80_map_regs(r0, r1, r2);')
    l('    }')
    l('    switch (op) {')

#-------------------------------------------------------------------------------
# write the end of the main switch-case
#
def write_op_post():
    l('      default: break;')
    l('    }')

#-------------------------------------------------------------------------------
# write source footer
#
def write_footer() :
    l('    map_bits &= ~(_BIT_USE_IX|_BIT_USE_IY);')
    l('    if (trap_addr != 0xFFFFFFFFFFFFFFFF) {')
    l('      uint64_t ta = trap_addr;')
    l('      for (int i = 0; i < Z80_MAX_NUM_TRAPS; i++) {')
    l('        ta >>= 16;')
    l('        if (((ta & 0xFFFF) == pc) && (pc != 0xFFFF)) {')
    l('          trap_id = i;')
    l('          break;')
    l('        }')
    l('      }')
    l('    }')
    l('  } while ((ticks < num_ticks) && (trap_id < 0));')
    l('  _S_PC(pc);')
    l('  r0 = _z80_flush_r0(ws, r0, r2);')
    l('  r1 = _z80_flush_r1(ws, r1, r2);')
    l('  r2 = (r2 & ~_BITS_MAP_REGS) | map_bits;')
    l('  cpu->bc_de_hl_fa = r0;')
    l('  cpu->wz_ix_iy_sp = r1;')
    l('  cpu->im_ir_pc_bits = r2;')
    l('  cpu->bc_de_hl_fa_ = r3;')
    l('  cpu->pins = pins;')
    l('  cpu->trap_id = trap_id;')
    l('  return ticks;')
    l('}')

#-------------------------------------------------------------------------------
#   Generate code for checking and handling an interrupt request at
#   the end of an instruction:
#
#   An interrupt response cycle looks a lot like an opcode fetch machine cycle.
#
#   NOTE: The INT pint is normally checked at the start of the last time-cycle
#   of an instruction. The emulator moves this check to the start
#   of the next time cycle (so it will check right *after* the last instruction
#   time-cycle.
#
#              T1   T2   TW   TW   T3   T4
#    --------+----+----+----+----+----+----+
#    CLK     |--**|--**|--**|--**|--**|--**|
#    INT    *|*   |    |    |    |    |    |
#    A15-A0  |        PC         |  RFRSH  |
#    M1      |****|****|****|****|    |    |
#    MREG    |    |    |    |    |  **|**  |
#    IORQ    |    |    |  **|****|    |    |
#    RD      |    |    |    |    |    |    |
#    WR      |    |    |    |    |    |    |
#    D7-D0   |    |    |    |  XX|XX..|    |
#    WAIT    |    |    |    | -- |    |    |
#    RFSH    |    |    |    |    |****|****|
#
#   Interrupt controllers must check for the M1|IORQ pin combination 
#   being set (with neither the RD nor WR being set, and the highest 
#   priority interrupt controller must place the interrupt vector on the
#   data bus.
#
#   INT MODE 1: 13 cycles
#   INT MODE 2: 19 cycles
#
def write_interrupt_handling():
    l('    if (((pins & (Z80_INT|Z80_BUSREQ))==Z80_INT) && (r2 & _BIT_IFF1)) {')
    l('      r2 &= ~(_BIT_IFF1|_BIT_IFF2);')
    l('      if (pins & Z80_HALT) {')
    l('        pins &= ~Z80_HALT;')
    l('        pc++;')
    l('      }')
    l('      _ON(Z80_M1|Z80_IORQ);')
    l('      _SA(pc);')
    l('      _TW(4);')
    l('      const uint8_t int_vec = _GD();')
    l('      _OFF(Z80_M1|Z80_IORQ);')
    l('      _BUMPR();')
    l('      _T(2);')
    l('      uint16_t sp = _G_SP();')
    l('      _MW(--sp,pc>>8);')
    l('      _MW(--sp,pc);')
    l('      _S_SP(sp);')
    l('      switch (_G_IM()) {')
    l('        case 0:')
    l('          break;')
    l('        case 1:')
    l('          pc = 0x0038;')
    l('          break;')
    l('        case 2:')
    l('          {')
    l('            addr = _G_I() | (int_vec & 0xFE);')
    l('            uint8_t z,w;')
    l('            _MR(addr++,z);')
    l('            _MR(addr,w);')
    l('            pc = (w<<8)|z;')
    l('          }')
    l('          break;')
    l('      }')
    l('      _S_WZ(pc);')
    l('    }')

#-------------------------------------------------------------------------------
# Write the ED extended instruction block.
#
def write_ed_ops():
    l('case 0xED: {')
    inc_indent()
    l('_FETCH(op);')
    l('switch(op) {')
    inc_indent()
    for i in range(0, 256):
        write_op(enc_ed_op(i))
    l('default: break;');
    dec_indent()
    l('}')
    dec_indent()
    l('}')
    l('break;')

#-------------------------------------------------------------------------------
# Return code to setup an address variable 'a' with the address of HL
# or (IX+d), (IY+d). For the index instructions also update WZ with
# IX+d or IY+d
#
def addr(ext_ticks) :
    return '_ADDR(addr,'+str(ext_ticks)+');'

#-------------------------------------------------------------------------------
# Return code to setup an variable 'addr' with the address of HL or (IX+d), (IY+d).
# For the index instructions, also update WZ with IX+d or IY+d
#
def iHLdsrc(ext) :
    return "FIXME!"

#-------------------------------------------------------------------------------
#   Flag computation helpers
#
def sz(val):
    return '_z80_sz('+val+')'

def szyxch(acc,val,res):
    return '_z80_szyxch('+acc+','+val+','+res+')'

def add_flags(acc,val,res):
    return '_z80_add_flags('+acc+','+val+','+res+')'

def sub_flags(acc,val,res):
    return '_z80_sub_flags('+acc+','+val+','+res+')'

def cp_flags(acc,val,res):
    return '_z80_cp_flags('+acc+','+val+','+res+')'

def sziff2(val):
    return '_z80_sziff2_flags('+sz(val)+'|('+val+'&(Z80_YF|Z80_XF))|(c.IFF2?Z80_PF:0))'

#-------------------------------------------------------------------------------
#   out_n_a
#
#   Generate code for OUT (n),A
#
def out_n_a():
    src = '{'
    src += '_IMM8(d8);'
    src += 'uint8_t a=_G_A();'
    src += 'addr=(a<<8)|d8;'
    src += '_OUT(addr,a);'
    src += 'addr=(addr&0xFF00)|((addr+1)&0x00FF);'
    src += '_S_WZ(addr);'
    src += '}'
    return src

#-------------------------------------------------------------------------------
#   in_A_n
#
#   Generate code for IN A,(n)
#
def in_n_a():
    src = '{'
    src += '_IMM8(d8);'
    src += 'uint8_t a=_G_();'
    src += 'addr=(a<<8)|d8;'
    src += '_IN(addr++,a);'
    src += '_S_A(a);'
    src += '_S_WZ(addr);'
    src += '}'
    return src

#-------------------------------------------------------------------------------
#   ex_sp_dd
#
#   Generate code for EX (SP),HL; EX (SP),IX and EX (SP),IY
#
def ex_sp_dd():
    src =tick()
    src+='{uint8_t w,z;'
    src+=rd('c.SP','z')
    src+=rd('c.SP+1','w')
    src+=wr('c.SP','(uint8_t)c.'+rp[2])
    src+=wr('c.SP+1','(uint8_t)(c.'+rp[2]+'>>8)')
    src+='c.'+rp[2]+'=c.WZ=(w<<8)|z;}'
    src+=tick(2)
    return src

#-------------------------------------------------------------------------------
#   exx
#
#   Generate code for EXX
#
def exx():
    src ='{'
    src+='r0=_z80_flush_r0(ws,r0,r2);'
    src+='const uint64_t rx=r3;'
    src+='r3=(r3&0xffff)|(r0&0xffffffffffff0000);'
    src+='r0=(r0&0xffff)|(rx&0xffffffffffff0000);'
    src+='ws=_z80_map_regs(r0, r1, r2);'
    src+='}'
    return src

#-------------------------------------------------------------------------------
#   pop_dd
#
#   Generate code for POP dd.
#
def pop_dd(p):
    src ='addr=_G_SP();'
    src+='_MR(addr++,d8);'
    # special case POP AF, F<=>A
    if p==3:
        src+='d16=d8<<8;'
    else:
        src+='d16=d8;'
    src+='_MR(addr++,d8);'
    if p==3:
        src+='d16|=d8;'
    else:
        src+='d16|=d8<<8;'
    src+='_S_'+rp2[p]+'(d16);'
    src+='_S_SP(addr);'
    return src

#-------------------------------------------------------------------------------
#   push_dd
#
#   Generate code for PUSH dd
#
def push_dd(p):
    src ='_T(1);'
    src+='addr=_G_SP();'
    src+='d16=_G_'+rp2[p]+'();'
    # special case PUSH AF, F<=>A
    if p==3:
        src+='_MW(--addr,d16);'
        src+='_MW(--addr,d16>>8);'
    else:
        src+='_MW(--addr,d16>>8);'
        src+='_MW(--addr,d16);'
    src+='_S_SP(addr);'
    return src

#-------------------------------------------------------------------------------
#   ld_inn_dd
#   LD (nn),dd
#
def ld_inn_dd(p):
    src  = '_IMM16(addr);'
    src += 'd16=_G_'+rp[p]+'();'
    src += '_MW(addr++,d16&0xFF);'
    src += '_MW(addr,d16>>8);'
    src += '_S_WZ(addr);'
    return src

#-------------------------------------------------------------------------------
#   ld_dd_inn
#   LD dd,(nn)
#
def ld_dd_inn(p):
    src  = '_IMM16(addr);'
    src += '_MR(addr++,d8);d16=d8;'
    src += '_MR(addr,d8);d16|=d8<<8;'
    src += '_S_'+rp[p]+'(d16);'
    src += '_S_WZ(addr);'
    return src

#-------------------------------------------------------------------------------
#   bit_n_idd
#
#   Generate code for BIT n,(HL); BIT n,(IX+d); BIT n,(IY+d)
#
#   Flag computation: the undocumented YF and XF flags are set from high byte 
#   of HL+1 or IX/IY+d
#
def bit_n_idd(ext, y):
    src =iHLdsrc(ext)
    src+=tick()
    src+=ext_ticks(ext,1)
    src+=rd('a','v')
    src+='v&='+hex(1<<y)+';'
    src+='f=Z80_HF|(v?(v&Z80_SF):(Z80_ZF|Z80_PF))|((c.WZ>>8)&(Z80_YF|Z80_XF));'
    src+='c.F=f|(c.F&Z80_CF);'
    return src

#-------------------------------------------------------------------------------
#   bit_n_r
#
#   Generate code for BIT n,r
#
def bit_n_r(y,z):
    src ='v=c.'+r[z]+'&'+hex(1<<y)+';'
    src+='f=Z80_HF|(v?(v&Z80_SF):(Z80_ZF|Z80_PF))|(c.'+r[z]+'&(Z80_YF|Z80_XF));'
    src+='c.F=f|(c.F&Z80_CF);'
    return src

#-------------------------------------------------------------------------------
#   res_n_idd
#
#   Generate code for RES n,(HL); RES n,(IX+d); RES n,(IY+d)
#
def res_n_idd(ext, y):
    src =iHLdsrc(ext)
    src+=tick()
    src+=ext_ticks(ext,1)
    src+=rd('a','v')
    src+=wr('a','v&~'+hex(1<<y))
    return src

#-------------------------------------------------------------------------------
#   res_n_idd_r
#
#   Generate code for RES n,(IX+d),r; RES n,(IY+d),r undocumented instructions
#
def res_n_idd_r(ext, y, z):
    src =iHLdsrc(ext)
    src+=tick()
    src+=ext_ticks(ext,1)
    src+=rd('a','v')
    src+='c.'+r[z]+'=v&~'+hex(1<<y)+';'
    src+=wr('a','c.'+r[z])
    return src

#-------------------------------------------------------------------------------
#   set_n_idd
#
#   Generate code for SET n,(HL); SET n,(IX+d); SET n,(IY+d)
#
def set_n_idd(ext, y):
    src =iHLdsrc(ext)
    src+=tick()
    src+=ext_ticks(ext,1)
    src+=rd('a','v')
    src+=wr('a','v|'+hex(1<<y))
    return src

#-------------------------------------------------------------------------------
#   set_n_idd_r
#
#   Generate code for SET n,(IX+d),r; SET n,(IY+d),r undocumented instructions
#
def set_n_idd_r(ext, y, z):
    src =iHLdsrc(ext)
    src+=tick()
    src+=ext_ticks(ext,1)
    src+=rd('a','v')
    src+='c.'+r[z]+'=v|'+hex(1<<y)+';'
    src+=wr('a','c.'+r[z])
    return src

#-------------------------------------------------------------------------------
#   call_nn
#
#   Generate code for CALL nn
#
def call_nn():
    src ='_IMM16(addr);'
    src+='_T(1);'
    src+='d16=_G_SP();'
    src+='_MW(--d16,pc>>8);'
    src+='_MW(--d16,pc);'
    src+='_S_SP(d16);'
    src+='pc=addr;'
    return src

#-------------------------------------------------------------------------------
#   call_cc_nn
#
#   Generate code for CALL cc,nn
#
def call_cc_nn(y):
    src =imm16()
    src+='if ('+cond[y]+'){'
    src+=tick()
    src+=wr('--c.SP','(uint8_t)(c.PC>>8)')
    src+=wr('--c.SP','(uint8_t)c.PC')
    src+='c.PC=c.WZ;'
    src+='}'
    return src

#-------------------------------------------------------------------------------
#   ldi
#
def ldi():
    src =rd('c.HL','v')
    src+=wr('c.DE','v')
    src+=tick(2)
    src+='v+=c.A;'
    src+='f=c.F&(Z80_SF|Z80_ZF|Z80_CF);'
    src+='if(v&0x02){f|=Z80_YF;}'
    src+='if(v&0x08){f|=Z80_XF;}'
    src+='c.HL++;c.DE++;c.BC--;'
    src+='if(c.BC){f|=Z80_VF;}'
    src+='c.F=f;'
    return src

#-------------------------------------------------------------------------------
#   ldir
#
def ldir():
    src=ldi()
    src+='if(c.BC){'
    src+='c.PC-=2;'
    src+='c.WZ=c.PC+1;'
    src+=tick(5)
    src+='}'
    return src

#-------------------------------------------------------------------------------
#   ldd
#
def ldd():
    src =rd('c.HL','v')
    src+=wr('c.DE','v')
    src+=tick(2)
    src+='v+=c.A;'
    src+='f=c.F&(Z80_SF|Z80_ZF|Z80_CF);'
    src+='if(v&0x02){f|=Z80_YF;}'
    src+='if(v&0x08){f|=Z80_XF;}'
    src+='c.HL--;c.DE--;c.BC--;'
    src+='if(c.BC){f|=Z80_VF;}'
    src+='c.F=f;'
    return src

#-------------------------------------------------------------------------------
#   lddr()
#
def lddr():
    src =ldd()
    src+='if(c.BC){'
    src+='c.PC-=2;'
    src+='c.WZ=c.PC+1;'
    src+=tick(5)
    src+='}'
    return src

#-------------------------------------------------------------------------------
#   cpi()
#
def cpi():
    src =rd('c.HL','v')
    src+=tick(5)
    src+='{int r=(int)c.A-v;'
    src+='f=Z80_NF|(c.F&Z80_CF)|'+sz('r')+';'
    src+='if((r&0x0F)>(c.A&0x0F)){'
    src+='f|=Z80_HF;'
    src+='r--;'
    src+='}'
    src+='if(r&0x02){f|=Z80_YF;}'
    src+='if(r&0x08){f|=Z80_XF;}'
    src+='}'
    src+='c.WZ++;c.HL++;c.BC--;'
    src+='if(c.BC){f|=Z80_VF;}'
    src+='c.F=f;'
    return src

#-------------------------------------------------------------------------------
#   cpir()
#
def cpir():
    src =cpi()
    src+='if(c.BC&&!(c.F&Z80_ZF)){'
    src+='c.PC-=2;'
    src+='c.WZ=c.PC+1;'   # FIXME: is this correct (see memptr_eng.txt)
    src+=tick(5)
    src+='}'
    return src

#-------------------------------------------------------------------------------
#   cpd()
#
def cpd():
    src =rd('c.HL','v')
    src+='{int r=(int)c.A-v;'
    src+=tick(5)
    src+='f=Z80_NF|(c.F&Z80_CF)|'+sz('r')+';'
    src+='if((r&0x0F)>(c.A&0x0F)){'
    src+='f|=Z80_HF;'
    src+='r--;'
    src+='}'
    src+='if(r&0x02){f|=Z80_YF;}'
    src+='if(r&0x08){f|=Z80_XF;}'
    src+='}'
    src+='c.WZ--;c.HL--;c.BC--;'
    src+='if(c.BC){f|=Z80_VF;}'
    src+='c.F=f;'
    return src

#-------------------------------------------------------------------------------
#   cpdr()
#
def cpdr():
    src =cpd()
    src+='if((c.BC)&&!(c.F&Z80_ZF)){'
    src+='c.PC-=2;'
    src+='c.WZ=c.PC+1;'
    src+=tick(5)
    src+='}'
    return src

#-------------------------------------------------------------------------------
#   ini_ind_flags(io_val,c_add)
#   outi_outd_flags(io_val,c_add)
#
#   Returns a string which evaluates the flags for ini and ind instructions into F.
#   NOTE: most INI/OUTI flag settings are undocumented in the official
#   docs, so this is taken from MAME, there's also more
#   information here: http://www.z80.info/z80undoc3.txt
#
def ini_ind_flags(io_val,c_add):
    src ='f=c.B?(c.B&Z80_SF):Z80_ZF;'
    src+='if('+io_val+'&Z80_SF){f|=Z80_NF;}'
    src+='{';
    src+='uint32_t t=(uint32_t)((c.C+('+c_add+'))&0xFF)+(uint32_t)'+io_val+';'
    src+='if(t&0x100){f|=(Z80_HF|Z80_CF);}'
    src+='f|=_z80_szp[((uint8_t)(t&0x07))^c.B]&Z80_PF;'
    src+='}'
    src+='c.F=f;'
    return src

def outi_outd_flags(io_val):
    src='f=c.B?(c.B&Z80_SF):Z80_ZF;'
    src+='if('+io_val+'&Z80_SF){f|=Z80_NF;}'
    src+='{';
    src+='uint32_t t=(uint32_t)c.L+(uint32_t)'+io_val+';'
    src+='if(t&0x100){f|=(Z80_HF|Z80_CF);}'
    src+='f|=_z80_szp[((uint8_t)(t&0x07))^c.B]&Z80_PF;'
    src+='}'
    src+='c.F=f;'
    return src

#-------------------------------------------------------------------------------
#   ini()
#
def ini():
    src =tick()
    src+='c.WZ=c.BC;'
    src+=inp('c.WZ++','v')
    src+='c.B--;'
    src+=wr('c.HL++','v')
    src+=ini_ind_flags('v','+1')
    return src

#-------------------------------------------------------------------------------
#   inir()
#
def inir():
    src =ini()
    src+='if(c.B){'
    src+='c.PC-=2;'
    src+=tick(5)
    src+='}'
    return src

#-------------------------------------------------------------------------------
#   ind()
#
def ind():
    src =tick()
    src+='c.WZ=c.BC;'
    src+=inp('c.WZ--','v')
    src+='c.B--;'
    src+=wr('c.HL--','v')
    src+=ini_ind_flags('v','-1')
    return src

#-------------------------------------------------------------------------------
#   indr()
#
def indr():
    src =ind()
    src+='if(c.B){'
    src+='c.PC-=2;'
    src+=tick(5)
    src+='}'
    return src

#-------------------------------------------------------------------------------
#   outi()
#
def outi():
    src =tick()
    src+=rd('c.HL++','v')
    src+='c.B--;'
    src+='c.WZ=c.BC;'
    src+=out('c.WZ++','v')
    src+=outi_outd_flags('v')
    return src

#-------------------------------------------------------------------------------
#   otir()
#
def otir():
    src =outi()
    src+='if(c.B){'
    src+='c.PC-=2;'
    src+=tick(5)
    src+='}'
    return src

#-------------------------------------------------------------------------------
#   outd()
#
def outd():
    src =tick()
    src+=rd('c.HL--','v')
    src+='c.B--;'
    src+='c.WZ=c.BC;'
    src+=out('c.WZ--','v')
    src+=outi_outd_flags('v')
    return src

#-------------------------------------------------------------------------------
#   otdr()
#
def otdr():
    src =outd()
    src+='if(c.B){'
    src+='c.PC-=2;'
    src+=tick(5)
    src+='}'
    return src

#-------------------------------------------------------------------------------
#   djnz()
#
def djnz():
    src =tick()
    src+='{int8_t d;'
    src+=rd('c.PC++','d')
    src+='if(--c.B>0){'
    src+='c.WZ=c.PC=c.PC+d;'
    src+=tick(5)
    src+='}'
    src+='}'
    return src

#-------------------------------------------------------------------------------
#   jr()
#
def jr():
    src ='{int8_t d;'
    src+=rd('c.PC++','d')
    src+='c.WZ=c.PC=c.PC+d;'
    src+='}'
    src+=tick(5)
    return src;

#-------------------------------------------------------------------------------
#   jr_cc()
#
def jr_cc(y):
    src ='{int8_t d;'
    src+=rd('c.PC++','d')
    src+='if('+cond[y-4]+'){'
    src+='c.WZ=c.PC=c.PC+d;'
    src+=tick(5)
    src+='}'
    src+='}'
    return src

#-------------------------------------------------------------------------------
#   ret()
#
def ret():
    src  = 'd16=_G_SP();'
    src += '_MR(d16++,d8);pc=d8<<8;'
    src += '_MR(d16++,d8);pc|=d8;'
    src += '_S_SP(d16);'
    src += '_S_WZ(pc);'
    return src

#-------------------------------------------------------------------------------
#   ret_cc()
#
def ret_cc(y):
    src =tick()
    src+='if('+cond[y]+'){'
    src+='uint8_t w,z;'
    src+=rd('c.SP++','z')
    src+=rd('c.SP++','w')
    src+='c.PC=c.WZ=(w<<8)|z;'
    src+='}'
    return src

#-------------------------------------------------------------------------------
#   rst()
#
def rst(y):
    src =wr('--c.SP','(uint8_t)(c.PC>>8)')
    src+=wr('--c.SP','(uint8_t)c.PC')
    src+='c.WZ=c.PC=(uint16_t)'+hex(y*8)+';'
    return src

#-------------------------------------------------------------------------------
#   in_ic()
#   IN (C)
#
def in_ic():
    src ='c.WZ=c.BC;'
    src+=inp('c.WZ++','v')
    src+='c.F=_z80_szp[v]|(c.F&Z80_CF);'
    return src

#-------------------------------------------------------------------------------
#   in_r_ic
#   IN r,(C)
#
def in_r_ic(y):
    src ='c.WZ=c.BC;'
    src+=inp('c.WZ++','c.'+r[y])
    src+='c.F=_z80_szp[c.'+r[y]+']|(c.F&Z80_CF);'
    return src

#-------------------------------------------------------------------------------
#   out_ic()
#   OUT (C)
#
def out_ic():
    src ='c.WZ=c.BC;'
    src+=out('c.WZ++','0')
    return src

#-------------------------------------------------------------------------------
#   out_r_ic()
#   OUT r,(C)
#
def out_r_ic(y):
    src ='c.WZ=c.BC;'
    src+=out('c.WZ++','c.'+r[y])
    return src

#-------------------------------------------------------------------------------
#   ALU funcs
#
def add8(val):
    src ='{'
    src+='int res=c.A+'+val+';'
    src+='c.F='+add_flags('c.A',val,'res')+';'
    src+='c.A=(uint8_t)res;'
    src+='}'
    return src

def adc8(val):
    src ='{'
    src+='int res=c.A+'+val+'+(c.F&Z80_CF);'
    src+='c.F='+add_flags('c.A',val,'res')+';'
    src+='c.A=(uint8_t)res;'
    src+='}'
    return src

def sub8(val):
    src ='{'
    src+='int res=(int)c.A-(int)'+val+';'
    src+='c.F='+sub_flags('c.A',val,'res')+';'
    src+='c.A=(uint8_t)res;'
    src+='}'
    return src

def sbc8(val):
    src ='{'
    src+='int res=(int)c.A-(int)'+val+'-(c.F&Z80_CF);'
    src+='c.F='+sub_flags('c.A',val,'res')+';'
    src+='c.A=(uint8_t)res;'
    src+='}'
    return src

def cp8(val):
    # NOTE: XF|YF are set from val, not from result
    src ='{'
    src+='int res=(int)c.A-(int)'+val+';'
    src+='c.F='+cp_flags('c.A',val,'res')+';'
    src+='}'
    return src

def and8(val):
    src='c.A&='+val+';c.F=_z80_szp[c.A]|Z80_HF;' 
    return src

def or8(val):
    src='c.A|='+val+';c.F=_z80_szp[c.A];' 
    return src

def xor8(val):
    src='c.A^='+val+';c.F=_z80_szp[c.A];' 
    return src

def alu8(y,val):
    if (y==0):
        return add8(val)
    elif (y==1):
        return adc8(val)
    elif (y==2):
        return sub8(val)
    elif (y==3):
        return sbc8(val)
    elif (y==4):
        return and8(val)
    elif (y==5):
        return xor8(val)
    elif (y==6):
        return or8(val)
    elif (y==7):
        return cp8(val)

def neg8():
    src ='v=c.A;c.A=0;'
    src+=sub8('v')
    return src

def inc8(val):
    src ='{'
    src+='uint8_t r='+val+'+1;'
    src+='f='+sz('r')+'|(r&(Z80_XF|Z80_YF))|((r^'+val+')&Z80_HF);'
    src+='if(r==0x80){f|=Z80_VF;}'
    src+='c.F=f|(c.F&Z80_CF);'
    src+=val+'=r;'
    src+='}'
    return src

def dec8(val):
    src ='{'
    src+='uint8_t r='+val+'-1;'
    src+='f=Z80_NF|'+sz('r')+'|(r&(Z80_XF|Z80_YF))|((r^'+val+')&Z80_HF);'
    src+='if(r==0x7F){f|=Z80_VF;}'
    src+='c.F=f|(c.F&Z80_CF);'
    src+=val+'=r;'
    src+='}'
    return src

#-------------------------------------------------------------------------------
#   16-bit add,adc,sbc
#
#   flags computation taken from MAME
#
def add16(acc,val):
    src ='{'
    src+='c.WZ='+acc+'+1;'
    src+='uint32_t r='+acc+'+'+val+';'
    src+='c.F=(c.F&(Z80_SF|Z80_ZF|Z80_VF))|'
    src+='((('+acc+'^r^'+val+')>>8)&Z80_HF)|'
    src+='((r>>16)&Z80_CF)|((r>>8)&(Z80_YF|Z80_XF));'
    src+=acc+'=r;'
    src+='}'
    src+=tick(7)
    return src

def adc16(acc,val):
    src ='{'
    src+='c.WZ='+acc+'+1;'
    src+='uint32_t r='+acc+'+'+val+'+(c.F&Z80_CF);'
    src+='c.F=((('+acc+'^r^'+val+')>>8)&Z80_HF)|'
    src+='((r>>16)&Z80_CF)|'
    src+='((r>>8)&(Z80_SF|Z80_YF|Z80_XF))|'
    src+='((r&0xFFFF)?0:Z80_ZF)|'
    src+='((('+val+'^'+acc+'^0x8000)&('+val+'^r)&0x8000)>>13);'
    src+=acc+'=r;'
    src+='}'
    src+=tick(7)
    return src

def sbc16(acc,val):
    src ='{'
    src+='c.WZ='+acc+'+1;'
    src+='uint32_t r='+acc+'-'+val+'-(c.F&Z80_CF);'
    src+='c.F=((('+acc+'^r^'+val+')>>8)&Z80_HF)|Z80_NF|'
    src+='((r>>16)&Z80_CF)|'
    src+='((r>>8)&(Z80_SF|Z80_YF|Z80_XF))|'
    src+='((r&0xFFFF)?0:Z80_ZF)|'
    src+='((('+val+'^'+acc+')&('+acc+'^r)&0x8000)>>13);'
    src+=acc+'=r;'
    src+='}'
    src+=tick(7)
    return src

#-------------------------------------------------------------------------------
#   rotate and shift functions
#
def rrd():
    src ='{uint8_t l,v;'
    src+='c.WZ=c.HL;'
    src+=rd('c.WZ++','v')
    src+='l=c.A&0x0F;'
    src+='c.A=(c.A&0xF0)|(v&0x0F);'
    src+='v=(v>>4)|(l<<4);'
    src+=tick(4)
    src+=wr('c.HL','v')
    src+='c.F=_z80_szp[c.A]|(c.F&Z80_CF);'
    src+='}'
    return src

def rld():
    src ='{uint8_t l,v;'
    src+='c.WZ=c.HL;'
    src+=rd('c.WZ++','v')
    src+='l=c.A&0x0F;'
    src+='c.A=(c.A&0xF0)|(v>>4);'
    src+='v=(v<<4)|l;'
    src+=tick(4)
    src+=wr('c.HL','v')
    src+='c.F=_z80_szp[c.A]|(c.F&Z80_CF);'
    src+='}'
    return src

def rlca():
    src ='{'
    src+='uint8_t r=c.A<<1|c.A>>7;'
    src+='c.F=(c.A>>7&Z80_CF)|(c.F&(Z80_SF|Z80_ZF|Z80_PF))|(r&(Z80_XF|Z80_YF));'
    src+='c.A=r;'
    src+='}'
    return src

def rrca():
    src ='{'
    src+='uint8_t r=c.A>>1|c.A<<7;'
    src+='c.F=(c.A&Z80_CF)|(c.F&(Z80_SF|Z80_ZF|Z80_PF))|(r&(Z80_YF|Z80_XF));'
    src+='c.A=r;'
    src+='}'
    return src

def rla():
    src ='{'
    src+='uint8_t r=c.A<<1|(c.F&Z80_CF);'
    src+='c.F=(c.A>>7&Z80_CF)|(c.F&(Z80_SF|Z80_ZF|Z80_PF))|(r&(Z80_YF|Z80_XF));'
    src+='c.A=r;'
    src+='}'
    return src

def rra():
    src ='{'
    src+='uint8_t r=c.A>>1|((c.F&Z80_CF)<<7);'
    src+='c.F=(c.A&Z80_CF)|(c.F&(Z80_SF|Z80_ZF|Z80_PF))|(r&(Z80_YF|Z80_XF));'
    src+='c.A=r;'
    src+='}'
    return src

def rlc(val):
    src ='{'
    src+='uint8_t r='+val+'<<1|'+val+'>>7;'
    src+='c.F=_z80_szp[r]|('+val+'>>7&Z80_CF);'
    src+=val+'=r;'
    src+='}'
    return src

def rrc(val):
    src ='{'
    src+='uint8_t r='+val+'>>1|'+val+'<<7;'
    src+='c.F=_z80_szp[r]|('+val+'&Z80_CF);'
    src+=val+'=r;'
    src+='}'
    return src

def rl(val):
    src ='{'
    src+='uint8_t r='+val+'<<1|(c.F&Z80_CF);'
    src+='c.F=('+val+'>>7&Z80_CF)|_z80_szp[r];'
    src+=val+'=r;'
    src+='}'
    return src

def rr(val):
    src ='{'
    src+='uint8_t r='+val+'>>1|((c.F & Z80_CF)<<7);'
    src+='c.F=('+val+'&Z80_CF)|_z80_szp[r];'
    src+=val+'=r;'
    src+='}'
    return src

def sla(val):
    src ='{'
    src+='uint8_t r='+val+'<<1;'
    src+='c.F=('+val+'>>7&Z80_CF)|_z80_szp[r];'
    src+=val+'=r;'
    src+='}'
    return src

def sra(val):
    src ='{'
    src+='uint8_t r='+val+'>>1|('+val+'&0x80);'
    src+='c.F=('+val+'&Z80_CF)|_z80_szp[r];'
    src+=val+'=r;'
    src+='}'
    return src

# undocuments, sll is identical to sla, but inserts a 1 into the LSB
def sll(val):
    src ='{'
    src+='uint8_t r=('+val+'<<1)|1;'
    src+='c.F=('+val+'>>7&Z80_CF)|_z80_szp[r];'
    src+=val+'=r;'
    src+='}'
    return src

def srl(val):
    src ='{'
    src+='uint8_t r='+val+'>>1;'
    src+='c.F=('+val+'&Z80_CF)|_z80_szp[r];'
    src+=val+'=r;'
    src+='}'
    return src

def rot(y,val):
    if y==0:
        return rlc(val)
    elif y==1:
        return rrc(val)
    elif y==2:
        return rl(val)
    elif y==3:
        return rr(val)
    elif y==4:
        return sla(val)
    elif y==5:
        return sra(val)
    elif y==6:
        return sll(val)
    elif y==7:
        return srl(val)

#-------------------------------------------------------------------------------
#   rot_idd
#
#   Generate code for ROT (HL); ROT (IX+d); ROT (IY+d)
#
def rot_idd(ext, y):
    src =iHLdsrc(ext)
    src+=tick()
    src+=ext_ticks(ext,1)
    src+=rd('a','v')
    src+=rot(y,'v')
    src+=wr('a','v')
    return src

#-------------------------------------------------------------------------------
#   rot_idd_r
#
#   Generate code for ROT (IX+d),r; ROT (IY+d),r undocumented instructions.
#
def rot_idd_r(y, z):
    src =iHLdsrc(True)
    src+=tick(2)
    src+=rd('a','v')
    src+=rot(y,'v')
    src+='c.'+r[z]+'=v;'
    src+=wr('a','v')
    return src

#-------------------------------------------------------------------------------
#   misc ops
#
def cpl():
    src ='c.A^=0xFF;'
    src+='c.F=(c.F&(Z80_SF|Z80_ZF|Z80_PF|Z80_CF))|Z80_HF|Z80_NF|(c.A&(Z80_YF|Z80_XF));'
    return src

def scf():
    return 'c.F=(c.F&(Z80_SF|Z80_ZF|Z80_YF|Z80_XF|Z80_PF))|Z80_CF|(c.A&(Z80_YF|Z80_XF));'

def ccf():
    return 'c.F=((c.F&(Z80_SF|Z80_ZF|Z80_YF|Z80_XF|Z80_PF|Z80_CF))|((c.F&Z80_CF)<<4)|(c.A&(Z80_YF|Z80_XF)))^Z80_CF;'

# DAA from MAME and http://www.z80.info/zip/z80-documented.pdf
def daa():
    src ='v=c.A;'
    src+='if(c.F&Z80_NF){'
    src+='if(((c.A&0xF)>0x9)||(c.F&Z80_HF)){v-=0x06;}'
    src+='if((c.A>0x99)||(c.F&Z80_CF)){v-=0x60;}'
    src+='}else{'
    src+='if(((c.A&0xF)>0x9)||(c.F&Z80_HF)){v+=0x06;}'
    src+='if((c.A>0x99)||(c.F&Z80_CF)){v+=0x60;}'
    src+='}'
    src+='c.F&=Z80_CF|Z80_NF;'
    src+='c.F|=(c.A>0x99)?Z80_CF:0;'
    src+='c.F|=(c.A^v)&Z80_HF;'
    src+='c.F|=_z80_szp[v];'
    src+='c.A=v;'
    return src

def halt():
    return '_ON(Z80_HALT);pc--;'

def di():
    return 'c.IFF1=c.IFF2=false;'

def ei():
    return 'c.ei_pending=true;'

def reti():
    # same as RET, but also set the virtual Z80_RETI pin
    src ='{uint8_t w,z;'
    src+='_ON(Z80_RETI);'
    src+=rd('c.SP++','z')
    src+=rd('c.SP++','w')
    src+='c.PC=c.WZ=(w<<8)|z;}'
    return src

#-------------------------------------------------------------------------------
# Encode a main instruction, or an DD or FD prefix instruction.
# Takes an opcode byte and returns an opcode object, for invalid instructions
# the opcode object will be in its default state (opcode.src==None).
# cc is the name of the cycle-count table.
#
def enc_op(op) :

    o = opcode(op)

    # split opcode byte into bit groups, these identify groups
    # or subgroups of instructions, or serve as register indices 
    #
    #   |xx|yyy|zzz|
    #   |xx|pp|q|zzz|
    x = op>>6
    y = (op>>3)&7
    z = op&7
    p = y>>1
    q = y&1

    #---- block 1: 8-bit loads, and HALT
    if x == 1:
        if y == 6:
            if z == 6:
                # special case: LD (HL),(HL) is HALT
                o.cmt = 'HALT'
                o.src = halt()
            else:
                # LD (HL),r; LD (IX+d),r; LD (IX+d),r
                o.cmt = 'LD (HL/IX+d/IY+d),'+r[z]
                # special case LD (IX+d),L LD (IX+d),H
                if z in [4,5]:
                    o.src = 'd8=_IDX()?_G8(r0,_'+r[z]+'):_G_'+r[z]+'();'
                else:
                    o.src = 'd8=_G_'+r[z]+'();'
                o.src += addr(5)+'_MW(addr,d8);'
        elif z == 6:
            # LD r,(HL); LD r,(IX+d); LD r,(IY+d)
            o.cmt = 'LD '+r[y]+',(HL/IX+d/IY+d)'
            o.src = addr(5)+'_MR(addr,d8);'
            if y in [4,5]:
                o.src += 'if(_IDX()){_S8(r0,_'+r[y]+',d8);}else{_S_'+r[y]+'(d8);}'
            else:
                o.src += '_S_'+r[y]+'(d8);'
        else:
            # LD r,s
            o.cmt = 'LD '+r[y]+','+r[z]
            o.src = '_S_'+r[y]+'(_G_'+r[z]+'());'

    #---- block 2: 8-bit ALU instructions (ADD, ADC, SUB, SBC, AND, XOR, OR, CP)
    #elif x == 2:
    #    if z == 6:
    #        # ALU (HL); ALU (IX+d); ALU (IY+d)
    #        o.cmt = alu_cmt[y]+' '+iHLcmt(ext)
    #        o.src = iHLsrc(ext)+ext_ticks(ext,5)+rd('a','v')+alu8(y,'v')
    #    else:
    #        # ALU r
    #        o.cmt = alu_cmt[y]+' '+r[z]
    #        o.src = alu8(y,'c.'+r[z])

    #---- block 0: misc ops
    elif x == 0:
        if z == 0:
            if y == 0:
                # NOP
                o.cmt = 'NOP'
                o.src = ' '
    #        elif y == 1:
    #             # EX AF,AF'
    #             o.cmt = "EX AF,AF'"
    #             o.src = swp16('c.AF','c.AF_')
    #        elif y == 2:
    #             # DJNZ d
    #             o.cmt = 'DJNZ'
    #             o.src = djnz()
    #        elif  y == 3:
    #             # JR d
    #             o.cmt = 'JR d'
    #             o.src = jr()
    #        else:
    #             # JR cc,d
    #             o.cmt = 'JR '+cond_cmt[y-4]+',d'
    #             o.src = jr_cc(y)
        elif z == 1:
            if q == 0:
                # 16-bit immediate loads
                o.cmt = 'LD '+rp[p]+',nn'
                o.src = '_IMM16(d16);_S_'+rp[p]+'(d16);'
    #         else :
    #             # ADD HL,rr; ADD IX,rr; ADD IY,rr
    #             o.cmt = 'ADD '+rp[2]+','+rp[p]
    #             o.src = add16('c.'+rp[2],'c.'+rp[p])
        elif z == 2:
            # indirect loads
            op_tbl = [
                [ 'LD (BC),A',          'addr=_G_BC();d8=_G_A();_MW(addr++,d8);_S_WZ((d8<<8)|(addr&0x00FF));' ],
                [ 'LD A,(BC)',          'addr=_G_BC();_MR(addr++,d8);_S_A(d8);_S_WZ(addr);' ],
                [ 'LD (DE),A',          'addr=_G_DE();d8=_G_A();_MW(addr++,d8);_S_WZ((d8<<8)|(addr&0x00FF));' ],
                [ 'LD A,(DE)',          'addr=_G_DE();_MR(addr++,d8);_S_A(d8);_S_WZ(addr);' ],
                [ 'LD (nn),'+rp[2],     '_IMM16(addr);_MW(addr++,_G_L());_MW(addr,_G_H());_S_WZ(addr);' ],
                [ 'LD '+rp[2]+',(nn)',  '_IMM16(addr);_MR(addr++,d8);_S_L(d8);_MR(addr,d8);_S_H(d8);_S_WZ(addr);' ],
                [ 'LD (nn),A',          '_IMM16(addr);d8=_G_A();_MW(addr++,d8);_S_WZ((d8<<8)|(addr&0x00FF));' ],
                [ 'LD A,(nn)',          '_IMM16(addr);_MR(addr++,d8);_S_A(d8);_S_WZ(addr);' ],
            ]
            o.cmt = op_tbl[y][0]
            o.src = op_tbl[y][1]
        elif z == 3:
            # 16-bit INC/DEC 
            if q == 0:
                o.cmt = 'INC '+rp[p]
                o.src = '_T(2);_S_'+rp[p]+'(_G_'+rp[p]+'()+1);'
            else:
                o.cmt = 'DEC '+rp[p]
                o.src = '_T(2);_S_'+rp[p]+'(_G_'+rp[p]+'()-1);'
    #    elif z == 4 or z == 5:
    #         cmt = 'INC' if z == 4 else 'DEC'
    #         if y == 6:
    #             # INC/DEC (HL)/(IX+d)/(IY+d)
    #             o.cmt = cmt+' '+iHLcmt(ext)
    #             fn = inc8('v') if z==4 else dec8('v')
    #             o.src = iHLsrc(ext)+ext_ticks(ext,5)+tick()+rd('a','v')+fn+wr('a','v')
    #         else:
    #             # INC/DEC r
    #             o.cmt = cmt+' '+r[y]
    #             o.src = inc8('c.'+r[y]) if z==4 else dec8('c.'+r[y])
        elif z == 6:
            if y == 6:
                # LD (HL),n; LD (IX+d),n; LD (IY+d),n
                o.cmt = 'LD (HL/IX+d/IY+d),n'
                o.src = addr(2) + '_IMM8(d8);_MW(addr,d8);'
            else:
                # LD r,n
                o.cmt = 'LD '+r[y]+',n'
                o.src = '_IMM8(d8);_S_'+r[y]+'(d8);'
    #    elif z == 7:
    #         # misc ops on A and F
    #         op_tbl = [
    #             [ 'RLCA', rlca() ],
    #             [ 'RRCA', rrca() ],
    #             [ 'RLA',  rla() ],
    #             [ 'RRA',  rra() ],
    #             [ 'DAA',  daa() ],
    #             [ 'CPL',  cpl() ],
    #             [ 'SCF',  scf() ],
    #             [ 'CCF',  ccf() ]
    #         ]
    #         o.cmt = op_tbl[y][0]
    #         o.src = op_tbl[y][1]

    #--- block 3: misc and extended ops
    elif x == 3:
        if z == 0:
            pass
    #         # RET cc
    #         o.cmt = 'RET '+cond_cmt[y]
    #         o.src = ret_cc(y)
        if z == 1:
            if q == 0:
                # POP BC,DE,HL,IX,IY,AF
                o.cmt = 'POP '+rp2[p]
                o.src = pop_dd(p)
            else:
                # misc ops
                op_tbl = [
                    [ 'RET', ret() ],
                    [ 'EXX', exx() ],
                    [ 'JP '+rp[2], 'pc=_G_HL();' ],
                    [ 'LD SP,'+rp[2], '_T(2);_S_SP(_G_HL());' ]
                ]
                o.cmt = op_tbl[p][0]
                o.src = op_tbl[p][1]
    #    if z == 2:
    #         # JP cc,nn
    #         o.cmt = 'JP {},nn'.format(cond_cmt[y])
    #         o.src = imm16()+'if ({}) {{ c.PC=c.WZ; }}'.format(cond[y])
    #    if z == 3:
    #         # misc ops
    #         op_tbl = [
    #             [ 'JP nn', imm16()+'c.PC=c.WZ;' ],
    #             [ None, None ], # CB prefix instructions
    #             [ 'OUT (n),A', out_n_a() ],
    #             [ 'IN A,(n)', in_n_a() ],
    #             [ 'EX (SP),'+rp[2], ex_sp_dd() ],
    #             [ 'EX DE,HL', swp16('c.DE','c.HL') ],
    #             [ 'DI', di() ],
    #             [ 'EI', ei() ]
    #         ]
    #         o.cmt = op_tbl[y][0]
    #         o.src = op_tbl[y][1]
    #    if z == 4:
    #         # CALL cc,nn
    #         o.cmt = 'CALL {},nn'.format(cond_cmt[y])
    #         o.src = call_cc_nn(y)
        if z == 5:
            if q == 0:
                # PUSH BC,DE,HL,IX,IY,AF
                o.cmt = 'PUSH {}'.format(rp2[p])
                o.src = push_dd(p)
            else:
                op_tbl = [
                    [ 'CALL nn', call_nn() ],
                    [ 'DD prefix', 'map_bits|=_BIT_USE_IX;continue;' ],
                    [ None, None ], # ED prefix instructions
                    [ 'FD prefix', 'map_bits|=_BIT_USE_IY;continue;'],
                ]
                o.cmt = op_tbl[p][0]
                o.src = op_tbl[p][1]
    #    if z == 6:
    #         # ALU n
    #         o.cmt = '{} n'.format(alu_cmt[y])
    #         o.src = rd('c.PC++','v')+alu8(y,'v')
    #    if z == 7:
    #         # RST
    #         o.cmt = 'RST {}'.format(hex(y*8))
    #         o.src = rst(y)

    return o

#-------------------------------------------------------------------------------
#   ED prefix instructions
#
def enc_ed_op(op) :
    o = opcode(op)
    cc = 'cc_ed'

    x = op>>6
    y = (op>>3)&7
    z = op&7
    p = y>>1
    q = y&1

    #if x == 2:
    #    # block instructions (LDIR etc)
    #    if y >= 4 and z < 4 :
    #        op_tbl = [
    #            [ 
    #                [ 'LDI',  ldi() ],
    #                [ 'LDD',  ldd() ],
    #                [ 'LDIR', ldir() ],
    #                [ 'LDDR', lddr() ]
    #            ],
    #            [
    #                [ 'CPI',  cpi() ],
    #                [ 'CPD',  cpd() ],
    #                [ 'CPIR', cpir() ],
    #                [ 'CPDR', cpdr() ]
    #            ],
    #            [
    #                [ 'INI',  ini() ],
    #                [ 'IND',  ind() ],
    #                [ 'INIR', inir() ],
    #                [ 'INDR', indr() ]
    #            ],
    #            [
    #                [ 'OUTI', outi() ],
    #                [ 'OUTD', outd() ],
    #                [ 'OTIR', otir() ],
    #                [ 'OTDR', otdr() ]
    #            ]
    #        ]
    #        o.cmt = op_tbl[z][y-4][0]
    #        o.src = op_tbl[z][y-4][1]

    if x == 1:
        # misc ops
        #if z == 0:
        #    # IN r,(C)
        #    if y == 6:
        #        # undocumented special case 'IN F,(C)', only alter flags, don't store result
        #        o.cmt = 'IN (C)';
        #        o.src = in_ic()
        #    else:
        #        o.cmt = 'IN {},(C)'.format(r[y])
        #        o.src = in_r_ic(y)
        #if z == 1:
        #    # OUT (C),r
        #    if y == 6:
        #        # undocumented special case 'OUT (C),F', always output 0
        #        o.cmd = 'OUT (C)';
        #        o.src = out_ic()
        #    else:
        #        o.cmt = 'OUT (C),{}'.format(r[y])
        #        o.src = out_r_ic(y)
        #if z == 2:
        #    # SBC/ADC HL,rr
        #    if q==0:
        #        o.cmt = 'SBC HL,'+rp[p]
        #        o.src = sbc16('c.HL','c.'+rp[p])
        #    else:
        #        o.cmt = 'ADC HL,'+rp[p]
        #        o.src = adc16('c.HL','c.'+rp[p])
        if z == 3:
            # 16-bit immediate address load/store
            if q == 0:
                o.cmt = 'LD (nn),{}'.format(rp[p])
                o.src = ld_inn_dd(p)
            else:
                o.cmt = 'LD {},(nn)'.format(rp[p])
                o.src = ld_dd_inn(p)
        #if z == 4:
        #    # NEG
        #    o.cmt = 'NEG'
        #    o.src = neg8()
        #if z == 5:
        #    # RETN, RETI (only RETI implemented!)
        #    if y == 1:
        #        o.cmt = 'RETI'
        #        o.src = reti()
        #if z == 6:
        #    # IM m
        #    im_mode = [ 0, 0, 1, 2, 0, 0, 1, 2 ]
        #    o.cmt = 'IM {}'.format(im_mode[y])
        #    o.src = 'c.IM={};'.format(im_mode[y])
        #if z == 7:
        #    # misc ops on I,R and A
        #    op_tbl = [
        #        [ 'LD I,A', tick()+'c.I=c.A;' ],
        #        [ 'LD R,A', tick()+'c.R=c.A;' ],
        #        [ 'LD A,I', tick()+'c.A=c.I; c.F='+sziff2('c.I')+'|(c.F&Z80_CF);' ],
        #        [ 'LD A,R', tick()+'c.A=c.R; c.F='+sziff2('c.R')+'|(c.F&Z80_CF);' ],
        #        [ 'RRD', rrd() ],
        #        [ 'RLD', rld() ],
        #        [ 'NOP (ED)', ' ' ],
        #        [ 'NOP (ED)', ' ' ],
        #    ]
        #    o.cmt = op_tbl[y][0]
        #    o.src = op_tbl[y][1]
    return o

#-------------------------------------------------------------------------------
#   CB prefix instructions
#
def enc_cb_op(op) :
    o = opcode(op)

    x = op>>6
    y = (op>>3)&7
    z = op&7

    # NOTE x==0 (ROT), x==1 (BIT), x==2 (RES) and x==3 (SET) instructions are
    # handled dynamically in the fallthrough path!
    return o

#-------------------------------------------------------------------------------
# indent and tab stuff
#
def inc_indent():
    global indent
    indent += 1

def dec_indent():
    global indent
    indent -= 1

def tab() :
    return ' '*TabWidth*indent

#-------------------------------------------------------------------------------
# generate code to dynamically decode a bit/res/set instruction (unextended)
#
def dyn_bit_res_set():
    l('{')
    l('  uint8_t* vptr;')
    l('  switch (opcode&7) {')
    l('    case 0: vptr=&c.B; break;')
    l('    case 1: vptr=&c.C; break;')
    l('    case 2: vptr=&c.D; break;')
    l('    case 3: vptr=&c.E; break;')
    l('    case 4: vptr=&c.H; break;')
    l('    case 5: vptr=&c.L; break;')
    l('    case 6: vptr=0; break;')
    l('    case 7: vptr=&c.A; break;')
    l('  }')
    l('  uint8_t y=(opcode>>3)&7;')
    l('  switch (opcode>>6) {')
    l('    case 0:')
    l('      /* ROT n,r */')
    l('      if (vptr) {')
    l('        switch (y) {')
    l('          case 0:/*RLC r*/{uint8_t r=*vptr<<1|*vptr>>7;c.F=_z80_szp[r]|(*vptr>>7&Z80_CF);*vptr=r;}break;')
    l('          case 1:/*RRC r*/{uint8_t r=*vptr>>1|*vptr<<7;c.F=_z80_szp[r]|(*vptr&Z80_CF);*vptr=r;}break;')
    l('          case 2:/*RL  r*/{uint8_t r=*vptr<<1|(c.F&Z80_CF);c.F=(*vptr>>7&Z80_CF)|_z80_szp[r];*vptr=r;}break;')
    l('          case 3:/*RR  r*/{uint8_t r=*vptr>>1|((c.F&Z80_CF)<<7);c.F=(*vptr&Z80_CF)|_z80_szp[r];*vptr=r;}break;')
    l('          case 4:/*SLA r*/{uint8_t r=*vptr<<1;c.F=(*vptr>>7&Z80_CF)|_z80_szp[r];*vptr=r;}break;')
    l('          case 5:/*SRA r*/{uint8_t r=*vptr>>1|(*vptr&0x80);c.F=(*vptr&Z80_CF)|_z80_szp[r];*vptr=r;}break;')
    l('          case 6:/*SLL r*/{uint8_t r=(*vptr<<1)|1;c.F=(*vptr>>7&Z80_CF)|_z80_szp[r];*vptr=r;}break;')
    l('          case 7:/*SRL r*/{uint8_t r=*vptr>>1;c.F=(*vptr&Z80_CF)|_z80_szp[r];*vptr=r;}break;')
    l('        }')
    l('      } else {')
    l('        switch (y) {')
    l('          case 0:/*RLC (HL)*/a=c.HL;_T(1);_MR(a,v);{uint8_t r=v<<1|v>>7;c.F=_z80_szp[r]|(v>>7&Z80_CF);v=r;}_MW(a,v);break;')
    l('          case 1:/*RRC (HL)*/a=c.HL;_T(1);_MR(a,v);{uint8_t r=v>>1|v<<7;c.F=_z80_szp[r]|(v&Z80_CF);v=r;}_MW(a,v);break;')
    l('          case 2:/*RL  (HL)*/a=c.HL;_T(1);_MR(a,v);{uint8_t r=v<<1|(c.F&Z80_CF);c.F=(v>>7&Z80_CF)|_z80_szp[r];v=r;}_MW(a,v);break;')
    l('          case 3:/*RR  (HL)*/a=c.HL;_T(1);_MR(a,v);{uint8_t r=v>>1|((c.F & Z80_CF)<<7);c.F=(v&Z80_CF)|_z80_szp[r];v=r;}_MW(a,v);break;')
    l('          case 4:/*SLA (HL)*/a=c.HL;_T(1);_MR(a,v);{uint8_t r=v<<1;c.F=(v>>7&Z80_CF)|_z80_szp[r];v=r;}_MW(a,v);break;')
    l('          case 5:/*SRA (HL)*/a=c.HL;_T(1);_MR(a,v);{uint8_t r=v>>1|(v&0x80);c.F=(v&Z80_CF)|_z80_szp[r];v=r;}_MW(a,v);break;')
    l('          case 6:/*SLL (HL)*/a=c.HL;_T(1);_MR(a,v);{uint8_t r=(v<<1)|1;c.F=(v>>7&Z80_CF)|_z80_szp[r];v=r;}_MW(a,v);break;')
    l('          case 7:/*SRL (HL)*/a=c.HL;_T(1);_MR(a,v);{uint8_t r=v>>1;c.F=(v&Z80_CF)|_z80_szp[r];v=r;}_MW(a,v);break;')
    l('        }')
    l('      }')
    l('      break;')
    l('    case 1:')
    l('      /* BIT n,r */')
    l('      if (vptr) {')
    l('        v=*vptr&(1<<y);f=Z80_HF|(v?(v&Z80_SF):(Z80_ZF|Z80_PF))|(*vptr&(Z80_YF|Z80_XF));c.F=f|(c.F&Z80_CF);')
    l('      } else {')
    l('        a=c.HL;_T(1);_MR(a,v);v&=(1<<y);f=Z80_HF|(v?(v&Z80_SF):(Z80_ZF|Z80_PF))|((c.WZ>>8)&(Z80_YF|Z80_XF));c.F=f|(c.F&Z80_CF);')
    l('      }')
    l('      break;')
    l('    case 2:')
    l('      /* RES n,r */')
    l('      if (vptr) {')
    l('        *vptr&=~(1<<y);')
    l('      } else {')
    l('        a=c.HL;_T(1);_MR(a,v);_MW(a,v&~(1<<y));')
    l('      }')
    l('      break;')
    l('    case 3:')
    l('      /* RES n,r */')
    l('      if (vptr) {')
    l('        *vptr|=(1<<y);')
    l('      } else {')
    l('        a=c.HL;_T(1);_MR(a,v);_MW(a,v|(1<<y));')
    l('      }')
    l('      break;')
    l('  }')
    l('}')

#-------------------------------------------------------------------------------
# generate code to dynamically decode a bit/res/set instruction (unextended)
#
def dyn_bit_res_set_ixiy():
    i = r[6]    # IX or IY
    l('{')
    l('  uint8_t* vptr;')
    l('  switch (opcode&7) {')
    l('    case 0: vptr=&c.B; break;')
    l('    case 1: vptr=&c.C; break;')
    l('    case 2: vptr=&c.D; break;')
    l('    case 3: vptr=&c.E; break;')
    l('    case 4: vptr=&c.H; break;')
    l('    case 5: vptr=&c.L; break;')
    l('    case 6: vptr=0; break;')
    l('    case 7: vptr=&c.A; break;')
    l('  }')
    l('  uint8_t y=(opcode>>3)&7;')
    l('  switch (opcode>>6) {')
    l('    case 0:')
    l('      /* ROT n,r */')
    l('      if (vptr) {')
    l('        switch (y) {')
    l('          case 0:/*RLC ('+i+'+d),r*/a=c.WZ=c.'+i+'+d;_T(2);_MR(a,v);{uint8_t r=v<<1|v>>7;c.F=_z80_szp[r]|(v>>7&Z80_CF);v=r;}*vptr=v;_MW(a,v);break;')
    l('          case 1:/*RRC ('+i+'+d),r*/a=c.WZ=c.'+i+'+d;_T(2);_MR(a,v);{uint8_t r=v>>1|v<<7;c.F=_z80_szp[r]|(v&Z80_CF);v=r;}*vptr=v;_MW(a,v);break;')
    l('          case 2:/*RL  ('+i+'+d),r*/a=c.WZ=c.'+i+'+d;_T(2);_MR(a,v);{uint8_t r=v<<1|(c.F&Z80_CF);c.F=(v>>7&Z80_CF)|_z80_szp[r];v=r;}*vptr=v;_MW(a,v);break;')
    l('          case 3:/*RR  ('+i+'+d),r*/a=c.WZ=c.'+i+'+d;_T(2);_MR(a,v);{uint8_t r=v>>1|((c.F & Z80_CF)<<7);c.F=(v&Z80_CF)|_z80_szp[r];v=r;}*vptr=v;_MW(a,v);break;')
    l('          case 4:/*SLA ('+i+'+d),r*/a=c.WZ=c.'+i+'+d;_T(2);_MR(a,v);{uint8_t r=v<<1;c.F=(v>>7&Z80_CF)|_z80_szp[r];v=r;}*vptr=v;_MW(a,v);break;')
    l('          case 5:/*SRA ('+i+'+d),r*/a=c.WZ=c.'+i+'+d;_T(2);_MR(a,v);{uint8_t r=v>>1|(v&0x80);c.F=(v&Z80_CF)|_z80_szp[r];v=r;}*vptr=v;_MW(a,v);break;')
    l('          case 6:/*SLL ('+i+'+d),r*/a=c.WZ=c.'+i+'+d;_T(2);_MR(a,v);{uint8_t r=(v<<1)|1;c.F=(v>>7&Z80_CF)|_z80_szp[r];v=r;}*vptr=v;_MW(a,v);break;')
    l('          case 7:/*SRL ('+i+'+d),r*/a=c.WZ=c.'+i+'+d;_T(2);_MR(a,v);{uint8_t r=v>>1;c.F=(v&Z80_CF)|_z80_szp[r];v=r;}*vptr=v;_MW(a,v);break;')
    l('        }')
    l('      } else {')
    l('        switch (y) {')
    l('          case 0:/*RLC ('+i+'+d)*/a=c.WZ=c.'+i+'+d;_T(2);_MR(a,v);{uint8_t r=v<<1|v>>7;c.F=_z80_szp[r]|(v>>7&Z80_CF);v=r;}_MW(a,v);break;')
    l('          case 1:/*RRC ('+i+'+d)*/a=c.WZ=c.'+i+'+d;_T(2);_MR(a,v);{uint8_t r=v>>1|v<<7;c.F=_z80_szp[r]|(v&Z80_CF);v=r;}_MW(a,v);break;')
    l('          case 2:/*RL  ('+i+'+d)*/a=c.WZ=c.'+i+'+d;_T(2);_MR(a,v);{uint8_t r=v<<1|(c.F&Z80_CF);c.F=(v>>7&Z80_CF)|_z80_szp[r];v=r;}_MW(a,v);break;')
    l('          case 3:/*RR  ('+i+'+d)*/a=c.WZ=c.'+i+'+d;_T(2);_MR(a,v);{uint8_t r=v>>1|((c.F & Z80_CF)<<7);c.F=(v&Z80_CF)|_z80_szp[r];v=r;}_MW(a,v);break;')
    l('          case 4:/*SLA ('+i+'+d)*/a=c.WZ=c.'+i+'+d;_T(2);_MR(a,v);{uint8_t r=v<<1;c.F=(v>>7&Z80_CF)|_z80_szp[r];v=r;}_MW(a,v);break;')
    l('          case 5:/*SRA ('+i+'+d)*/a=c.WZ=c.'+i+'+d;_T(2);_MR(a,v);{uint8_t r=v>>1|(v&0x80);c.F=(v&Z80_CF)|_z80_szp[r];v=r;}_MW(a,v);break;')
    l('          case 6:/*SLL ('+i+'+d)*/a=c.WZ=c.'+i+'+d;_T(2);_MR(a,v);{uint8_t r=(v<<1)|1;c.F=(v>>7&Z80_CF)|_z80_szp[r];v=r;}_MW(a,v);break;')
    l('          case 7:/*SRL ('+i+'+d)*/a=c.WZ=c.'+i+'+d;_T(2);_MR(a,v);{uint8_t r=v>>1;c.F=(v&Z80_CF)|_z80_szp[r];v=r;}_MW(a,v);break;')
    l('        }')
    l('      }')
    l('      break;')
    l('    case 1:')
    l('      /* BIT n,(IX|IY+d) */')
    l('      a=c.WZ=c.'+i+'+d;_T(2);_MR(a,v);v&=(1<<y);f=Z80_HF|(v?(v&Z80_SF):(Z80_ZF|Z80_PF))|((c.WZ>>8)&(Z80_YF|Z80_XF));c.F=f|(c.F&Z80_CF);')
    l('      break;')
    l('    case 2:')
    l('      if (vptr) {')
    l('        /* RES n,(IX|IY+d),r (undocumented) */')
    l('        a=c.WZ=c.'+i+'+d;_T(2);_MR(a,v);*vptr=v&~(1<<y);_MW(a,*vptr);')
    l('      } else {')
    l('        /* RES n,(IX|IY+d) */')
    l('        a=c.WZ=c.'+i+'+d;_T(2);_MR(a,v);_MW(a,v&~(1<<y));')
    l('      }')
    l('      break;')
    l('    case 3:')
    l('      if (vptr) {')
    l('        /* SET n,(IX|IY+d),r (undocumented) */')
    l('        a=c.WZ=c.'+i+'+d;_T(2);_MR(a,v);*vptr=v|(1<<y);_MW(a,*vptr);')
    l('      } else {')
    l('        /* RES n,(IX|IY+d) */')
    l('        a=c.WZ=c.'+i+'+d;_T(2);_MR(a,v);_MW(a,v|(1<<y));')
    l('      }')
    l('      break;')
    l('  }')
    l('}')

#-------------------------------------------------------------------------------
# write a single (writes a case inside the current switch)
#
def write_op(op) :
    if op.src :
        if not op.cmt:
            op.cmt='???'
        l('case '+hex(op.byte)+':/*'+op.cmt+'*/'+op.src+'break;')

#-------------------------------------------------------------------------------
# main encoder function, this populates all the opcode tables and
# generates the C++ source code into the file f
#
Out = open(OutPath, 'w')
write_header()

# loop over all instruction bytes
indent = 3
for i in range(0, 256):
    # ED prefix instructions
    if i == 0xED:
        write_ed_ops()
    # CB prefix instructions
    elif i == 0xCB:
        pass
    # non-prefixed instruction
    else:
        write_op(enc_op(i))
indent = 0
write_op_post()
write_interrupt_handling()
write_footer()
Out.close()
