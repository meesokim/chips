#pragma once
/*#
    # spc1000.h

    Samsung Personal Computer 8bit SPC-1000 emulator in a C header.

    Do this:
    ~~~C
    #define CHIPS_IMPL
    ~~~
    before you include this file in *one* C or C++ file to create the 
    implementation.

    Optionally provide the following macros with your own implementation
    
    ~~~C
    CHIPS_ASSERT(c)
    ~~~
        your own assert macro (default: assert(c))

    You need to include the following headers before including spc1000.h:

    - chips/z80.h
    - chips/mc6847.h
    - chips/ay38910.h
    - chips/mem.h
    - chips/kbd.h
    - chips/clk.h

    ## The Samsung SPC-1000

    FIXME!

    ## TODO

    X- VIA emulation is currently only minimal
    X- handle shift key (some games use this as jump button)
    X- spc1000MMC is very incomplete (only what's needed for joystick)

    ## zlib/libpng license

    Copyright (c) 2018 Andre Weissflog
    This software is provided 'as-is', without any express or implied warranty.
    In no event will the authors be held liable for any damages arising from the
    use of this software.
    Permission is granted to anyone to use this software for any purpose,
    including commercial applications, and to alter it and redistribute it
    freely, subject to the following restrictions:
        1. The origin of this software must not be misrepresented; you must not
        claim that you wrote the original software. If you use this software in a
        product, an acknowledgment in the product documentation would be
        appreciated but is not required.
        2. Altered source versions must be plainly marked as such, and must not
        be misrepresented as being the original software.
        3. This notice may not be removed or altered from any source
        distribution. 
*/
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SPC1K_MAX_AUDIO_SAMPLES (1024)       /* max number of audio samples in internal sample buffer */
#define SPC1K_DEFAULT_AUDIO_SAMPLES (128)    /* default number of samples in internal sample buffer */
#define SPC1K_MAX_TAPE_SIZE (1<<28)          /* max size of tape file in bytes */

/* SPC-1000 models */
typedef enum {
    SPC1000,
    SPC1000A,
} spc1000_type_t;

/* joystick emulation types */
typedef enum {
    SPC1K_JOYSTICKTYPE_NONE,
    SPC1K_JOYSTICKTYPE_MMC
} spc1000_joystick_type_t;

/* joystick mask bits */
#define SPC1K_JOYSTICK_RIGHT (1<<0)
#define SPC1K_JOYSTICK_LEFT  (1<<1)
#define SPC1K_JOYSTICK_DOWN  (1<<2)
#define SPC1K_JOYSTICK_UP    (1<<3)
#define SPC1K_JOYSTICK_BTN   (1<<4)

/* audio sample data callback */
typedef void (*spc1000_audio_callback_t)(const float* samples, int num_samples, void* user_data);

/* configuration parameters for spc1000_init() */
typedef struct {
    spc1000_type_t type;
    spc1000_joystick_type_t joystick_type;     /* what joystick type to emulate, default is SPC1K_JOYSTICK_NONE */

    /* video output config */
    void* pixel_buffer;         /* pointer to a linear RGBA8 pixel buffer, at least 320*256*4 bytes */
    int pixel_buffer_size;      /* size of the pixel buffer in bytes */

    /* optional user-data for callbacks */
    void* user_data;

    /* audio output config (if you don't want audio, set audio_cb to zero) */
    spc1000_audio_callback_t audio_cb;   /* called when audio_num_samples are ready */
    int audio_num_samples;          /* default is ZX_AUDIO_NUM_SAMPLES */
    int audio_sample_rate;          /* playback sample rate, default is 44100 */
    float audio_volume;             /* audio volume: 0.0..1.0, default is 0.25 */
    
    /* ROM images */
    const void* rom_spc1000;
    int rom_spc1000_size;
    
    /* Tape image */
    const char* tap_spc1000;
    int tap_spc1000_size;
} spc1000_desc_t;

/* Samsung spc1000 emulation state */
typedef struct {
    z80_t cpu;    
    mc6847_t vdg;
    ay38910_t ay;
    beeper_t beeper;
    bool valid;
    bool out_cass0;
    bool out_cass1;
    spc1000_type_t type;
    spc1000_joystick_type_t joystick_type;
    uint8_t kbd_joymask;        /* joystick mask from keyboard-joystick-emulation */
    uint8_t joy_joymask;        /* joystick mask from calls to spc1000_joystick() */
    uint8_t mmc_cmd;
    uint8_t mmc_latch;
    uint8_t gmode;
    uint8_t iplk;
    bool fs;
    uint32_t tick_count;
    uint32_t motor_start;
    clk_t clk;
    mem_t mem;
    kbd_t kbd;
    void* user_data;
    spc1000_audio_callback_t audio_cb;
    int num_samples;
    int sample_pos;
    float sample_buffer[SPC1K_MAX_AUDIO_SAMPLES];
    uint8_t ram[0x10000];
    uint8_t vram[0x2000];
    uint8_t rom[0x8000];
    /* tape loading */
    int tape_size;  /* tape_size is > 0 if a tape is inserted */
    int tape_pos;
    uint8_t tape_buf[SPC1K_MAX_TAPE_SIZE];
    bool tapeMotor;
    bool pulse;
    bool printStatus;
    uint8_t tap;
    float speed;
} spc1000_t;

/* initialize a new spc1000 instance */
void spc1000_init(spc1000_t* sys, const spc1000_desc_t* desc);
/* discard spc1000 instance */
void spc1000_discard(spc1000_t* sys);
/* get the standard framebuffer width and height in pixels */
int spc1000_std_display_width(void);
int spc1000_std_display_height(void);
/* get the maximum framebuffer size in number of bytes */
int spc1000_max_display_size(void);
/* get the current framebuffer width and height in pixels */
int spc1000_display_width(spc1000_t* sys);
int spc1000_display_height(spc1000_t* sys);
/* reset spc1000 instance */
void spc1000_reset(spc1000_t* sys);
/* run spc1000 instance for a number of microseconds */
void spc1000_exec(spc1000_t* sys, uint32_t micro_seconds);
/* send a key down event */
void spc1000_key_down(spc1000_t* sys, int key_code);
/* send a key up event */
void spc1000_key_up(spc1000_t* sys, int key_code);
/* enable/disable joystick emulation */
void spc1000_set_joystick_type(spc1000_t* sys, spc1000_joystick_type_t type);
/* get current joystick emulation type */
spc1000_joystick_type_t spc1000_joystick_type(spc1000_t* sys);
/* set joystick mask (combination of SPC1K_JOYSTICK_*) */
void spc1000_joystick(spc1000_t* sys, uint8_t mask);
/* insert a tape for loading (must be an spc1000 TAP file), data will be copied */
bool spc1000_insert_tape(spc1000_t* sys, const uint8_t* ptr, int num_bytes);
/* remove tape */
void spc1000_remove_tape(spc1000_t* sys);
/* load a ZX Z80 file into the emulator */
bool spc1000_quickload(spc1000_t* sys, const uint8_t* ptr, int num_bytes); 

static uint8_t _ay38910_callback(int port_id, void* user_data);


#ifdef __cplusplus
} /* extern "C" */
#endif

/*-- IMPLEMENTATION ----------------------------------------------------------*/
#ifdef CHIPS_IMPL
#include <string.h>
#ifndef CHIPS_ASSERT
    #include <assert.h>
    #define CHIPS_ASSERT(c) assert(c)
#endif

#define _SPC1K_FREQUENCY (4000000)

static uint64_t _spc1000_tick(int num, uint64_t pins, void* user_data);
static uint64_t _spc1000_vdg_fetch(uint64_t pins, void* user_data);
static void _spc1000_init_keymap(spc1000_t* sys);
static void _spc1000_init_memorymap(spc1000_t* sys);
static void _spc1000_osload(spc1000_t* sys);

#define _SPC1K_DEFAULT(val,def) (((val) != 0) ? (val) : (def))
#define _SPC1K_CLEAR(val) memset(&val, 0, sizeof(val))

#define STONE 100/2
#define LTONE (STONE*2)

#include <stdio.h>

uint8_t _ay8910_read_callback(int port_id, void* user_data)
{
    spc1000_t *sys = (spc1000_t *) user_data;
    uint8_t val = 0;
    uint8_t *tap = &(sys->tap);
    if (sys && port_id == AY38910_PORT_A)
    {
        if (sys->tapeMotor)
        {
            int t = (sys->tick_count - sys->motor_start) >> 5;
            if (t > (*tap ? LTONE : STONE))
            {
                *tap = sys->tape_buf[sys->tape_pos++] == '1';
                if (sys->tape_pos > sys->tape_size)
                    sys->tape_pos = 0;
                sys->motor_start = sys->tick_count;
				t = 0;
            }
			else
			{
				if (t > (*tap ? STONE : STONE / 2))
					val = 1; // high
				else
					val = 0; // low
			}
//			printf("%d,%d,%d\n", val, t, *tap);
        }
		val = (val > 0) << 7 | !sys->tapeMotor << 6 | sys->printStatus << 2;
	}
    return val;
}

void spc1000_init(spc1000_t* sys, const spc1000_desc_t* desc) {
    CHIPS_ASSERT(sys && desc);
    CHIPS_ASSERT(desc->pixel_buffer && (desc->pixel_buffer_size >= spc1000_max_display_size()));

    memset(sys, 0, sizeof(spc1000_t));
    sys->valid = true;
    sys->joystick_type = desc->joystick_type;
    sys->user_data = desc->user_data;
    sys->audio_cb = desc->audio_cb;
	sys->tapeMotor = false;
    sys->speed = 1.0;
    sys->num_samples = _SPC1K_DEFAULT(desc->audio_num_samples, SPC1K_DEFAULT_AUDIO_SAMPLES);
    CHIPS_ASSERT(sys->num_samples <= SPC1K_MAX_AUDIO_SAMPLES);
    CHIPS_ASSERT(desc->rom_spc1000 && (desc->rom_spc1000_size == sizeof(sys->rom)));
    memcpy(sys->rom, desc->rom_spc1000, sizeof(sys->rom));

    /* initialize the hardware */
    clk_init(&sys->clk, _SPC1K_FREQUENCY);

    z80_desc_t cpu_desc;
    _SPC1K_CLEAR(cpu_desc);
    cpu_desc.tick_cb = _spc1000_tick;
    cpu_desc.user_data = sys;
    z80_init(&sys->cpu, &cpu_desc);

    mc6847_desc_t vdg_desc;
    _SPC1K_CLEAR(vdg_desc);
    vdg_desc.tick_hz = 3579545;
    vdg_desc.rgba8_buffer = (uint32_t*) desc->pixel_buffer;
    vdg_desc.rgba8_buffer_size = desc->pixel_buffer_size;
    vdg_desc.fetch_cb = _spc1000_vdg_fetch;
    vdg_desc.user_data = sys;
    mc6847_init(&sys->vdg, &vdg_desc);

    const int audio_hz = _SPC1K_DEFAULT(desc->audio_sample_rate, 44100);
    const float audio_vol = _SPC1K_DEFAULT(desc->audio_volume, 0.5f);
    beeper_init(&sys->beeper, _SPC1K_FREQUENCY, audio_hz, audio_vol);

    /* Sound AY-3-8910 state */
    ay38910_desc_t ay_desc;
    _SPC1K_CLEAR(ay_desc);
    ay_desc.type = AY38910_TYPE_8912;
    ay_desc.tick_hz = _SPC1K_FREQUENCY / 2;
    ay_desc.sound_hz = audio_hz;
    ay_desc.magnitude = _SPC1K_DEFAULT(desc->audio_volume, 0.5f);
    /* setup cassette tape */
    ay_desc.user_data = sys;
    ay_desc.in_cb = _ay8910_read_callback;
    
    spc1000_insert_tape(sys, desc->tap_spc1000, desc->tap_spc1000_size); 
    ay38910_init(&sys->ay, &ay_desc); 
    
    /* setup memory map and keyboard matrix */
    _spc1000_init_memorymap(sys);
    _spc1000_init_keymap(sys);

    /* CPU start state */
    z80_set_pc(&sys->cpu, 0x0000);
}

void spc1000_discard(spc1000_t* sys) {
    CHIPS_ASSERT(sys && sys->valid);
    sys->valid = false;
}

int spc1000_std_display_width(void) {
    return MC6847_DISPLAY_WIDTH;
}

int spc1000_std_display_height(void) {
    return MC6847_DISPLAY_HEIGHT;
}

int spc1000_max_display_size(void) {
    return MC6847_DISPLAY_WIDTH * MC6847_DISPLAY_HEIGHT * 4;
}

int spc1000_display_width(spc1000_t* sys) {
    CHIPS_ASSERT(sys && sys->valid);
    return MC6847_DISPLAY_WIDTH;
}

int spc1000_display_height(spc1000_t* sys) {
    CHIPS_ASSERT(sys && sys->valid);
    return MC6847_DISPLAY_HEIGHT;
}

void spc1000_reset(spc1000_t* sys) {
    CHIPS_ASSERT(sys && sys->valid);
    z80_reset(&sys->cpu);
    mc6847_reset(&sys->vdg);
    beeper_reset(&sys->beeper);
    _spc1000_init_memorymap(sys);
    z80_set_pc(&sys->cpu, 0x0000);
    sys->iplk = 0;
}

void spc1000_exec(spc1000_t* sys, uint32_t micro_seconds) {
    CHIPS_ASSERT(sys && sys->valid);
    uint32_t ticks_to_run = clk_ticks_to_run(&sys->clk, micro_seconds);
    uint32_t ticks_executed = z80_exec(&sys->cpu, ticks_to_run);
    clk_ticks_executed(&sys->clk, ticks_executed);
    kbd_update(&sys->kbd); 
}

void spc1000_key_down(spc1000_t* sys, int key_code) {
    CHIPS_ASSERT(sys && sys->valid);
    switch (sys->joystick_type) {
        case SPC1K_JOYSTICKTYPE_NONE:
            kbd_key_down(&sys->kbd, key_code);
            break;
        case SPC1K_JOYSTICKTYPE_MMC:
            switch (key_code) {
                case 0x20:  sys->kbd_joymask |= SPC1K_JOYSTICK_BTN; break;
                case 0x08:  sys->kbd_joymask |= SPC1K_JOYSTICK_LEFT; break;
                case 0x09:  sys->kbd_joymask |= SPC1K_JOYSTICK_RIGHT; break;
                case 0x0A:  sys->kbd_joymask |= SPC1K_JOYSTICK_DOWN; break;
                case 0x0B:  sys->kbd_joymask |= SPC1K_JOYSTICK_UP; break;
                default:    kbd_key_down(&sys->kbd, key_code); break;
            }
            break;
    }
}

void spc1000_key_up(spc1000_t* sys, int key_code) {
    CHIPS_ASSERT(sys && sys->valid);
    switch (sys->joystick_type) {
        case SPC1K_JOYSTICKTYPE_NONE:
            kbd_key_up(&sys->kbd, key_code);
            break;
        case SPC1K_JOYSTICKTYPE_MMC:
            switch (key_code) {
                case 0x20:  sys->kbd_joymask &= ~SPC1K_JOYSTICK_BTN; break;
                case 0x08:  sys->kbd_joymask &= ~SPC1K_JOYSTICK_LEFT; break;
                case 0x09:  sys->kbd_joymask &= ~SPC1K_JOYSTICK_RIGHT; break;
                case 0x0A:  sys->kbd_joymask &= ~SPC1K_JOYSTICK_DOWN; break;
                case 0x0B:  sys->kbd_joymask &= ~SPC1K_JOYSTICK_UP; break;
                default:    kbd_key_up(&sys->kbd, key_code); break;
            }
            break;
    }
}

void spc1000_set_joystick_type(spc1000_t* sys, spc1000_joystick_type_t type) {
    CHIPS_ASSERT(sys && sys->valid);
    sys->joystick_type = type;
}

spc1000_joystick_type_t spc1000_joystick_type(spc1000_t* sys) {
    CHIPS_ASSERT(sys && sys->valid);
    return sys->joystick_type;
}

void spc1000_joystick(spc1000_t* sys, uint8_t mask) {
    CHIPS_ASSERT(sys && sys->valid);
    sys->joy_joymask = mask;
}


/* CPU tick callback */
static uint64_t _spc1000_tick(int num_ticks, uint64_t pins, void* user_data) {
    spc1000_t* sys = (spc1000_t*) user_data;

    /* tick the video chip */
    mc6847_tick(&sys->vdg);
    if (!sys->fs && ((&sys->vdg)->pins & MC6847_FS))
    {
        pins |= Z80_INT;
        sys->fs = true;
    }
    if (!((&sys->vdg)->pins & MC6847_FS))
    {
        sys->fs = false;
    }
    /* tick audio systems */
    for (int i = 0; i < num_ticks; i++) {
        sys->tick_count++;
        bool sample_ready = beeper_tick(&sys->beeper);
        /* the AY-3-8912 chip runs at half CPU frequency */
        if (sys->tick_count & 1) {
            ay38910_tick(&sys->ay);
        }
        if (sample_ready) {
            float sample = sys->beeper.sample;
            sample += sys->ay.sample;
            sys->sample_buffer[sys->sample_pos++] = sample;
            if (sys->sample_pos == sys->num_samples) {
                if (sys->audio_cb) {
                    sys->audio_cb(sys->sample_buffer, sys->num_samples, sys->user_data);
                }
                sys->sample_pos = 0;
            }
        }
    }    

    /* memory and IO requests */
    if (pins & Z80_MREQ) 
    {
        const uint16_t addr = Z80_GET_ADDR(pins);
		uint8_t data = Z80_GET_DATA(pins);
        if (pins & Z80_RD) {
            Z80_SET_DATA(pins, !sys->iplk ? sys->rom[addr&0x7fff] : sys->ram[addr]);
        }
        else if (pins & Z80_WR) {
            sys->ram[addr] = Z80_GET_DATA(pins);
        }
    }
    else if (pins & Z80_IORQ) 
    {
        const uint16_t Port = Z80_GET_ADDR(pins);
        if (pins & Z80_RD) {
            if (Port >= 0x8000 && Port <= 0x8009) {
               // Z80_SET_DATA(pins, &sys->keyMatrix[Port - 0x8009]);
               Z80_SET_DATA(pins, kbd_scanlines(&sys->kbd, 1<<(Port-0x8000)));
            }
            else if ((Port & 0xe000) == 0x2000)
            {
                Z80_SET_DATA(pins, sys->gmode);
            }
            else if (Port < 0x2000)
            {
                Z80_SET_DATA(pins, sys->vram[Port & 0x1fff]);
            }
            else if ((Port & 0xFFFE) == 0x4000)
            {
                /* read from AY-3-8912 (11............0.) */
                pins = ay38910_iorq(&sys->ay, AY38910_BC1|pins) & Z80_PIN_MASK;
            }
            else if ((Port & 0xe000) == 0xa000)
            {
                sys->iplk = !sys->iplk;
            }
			else
				Z80_SET_DATA(pins, 0xff);
        }
        else if (pins & Z80_WR) {
            // an IO write
            const uint8_t data = Z80_GET_DATA(pins);
            const uint16_t Port = Z80_GET_ADDR(pins);            
            if (Port < 0x2000) 
            {
                sys->vram[Port] = data;
            }
            else if ((Port & 0xe000) == 0xa000)
            {
                sys->iplk = !sys->iplk;
            }
            else if ((Port & 0xE000) == 0x2000)	// GMODE setting
            {
#define CHECK(a, b, c) ((a & (1 << b)) ? c : 0)                
                uint64_t vdg_pins = CHECK(data, 2, MC6847_GM0) | CHECK(data, 1, MC6847_GM1) | CHECK(data, 3, MC6847_AG) | CHECK(data, 7, MC6847_CSS) | MC6847_GM2;
                uint64_t vdg_mask = MC6847_AG|MC6847_GM0|MC6847_GM1|MC6847_CSS|MC6847_GM2;
                mc6847_ctrl(&sys->vdg, vdg_pins, vdg_mask);
				sys->gmode = data;
            }
            else if ((Port & 0xFFFF) == 0x4000) // PSG
            {
                /* select AY-3-8912 register (11............0.) */
                ay38910_iorq(&sys->ay, AY38910_BDIR|AY38910_BC1|pins);
            } else if ((Port & 0xFFFF) == 0x4001) // PSG Write
            {
                /* write to AY-3-8912 (10............0.) */
                ay38910_iorq(&sys->ay, AY38910_BDIR|pins);
            }
            else if ((Port & 0xe000) == 0x6000)
            {
                if (data & 0x2)
                {
                    sys->pulse = !sys->pulse; 
                } else if (sys->pulse)
                {
                    sys->tapeMotor = !sys->tapeMotor;
                    if (sys->tapeMotor)
                    {
                        sys->motor_start = sys->tick_count;
                        sys->speed = 10.0;
                    }
                    else
                    {
                        sys->motor_start = 0;
                        sys->speed = 1.0;
                    }
                }
            }
        }
    }
    return pins;
}

#define ATTR_INV 0x1 // white
#define ATTR_CSS 0x2 // cyan blue
#define ATTR_SEM 0x4
#define ATTR_EXT 0x8

uint64_t _spc1000_vdg_fetch(uint64_t pins, void* user_data) {
    spc1000_t* sys = (spc1000_t*) user_data;
    const uint16_t addr = MC6847_GET_ADDR(pins);
    uint8_t data = sys->vram[(addr & 0x1fff)];
    MC6847_SET_DATA(pins, data);
    if (!(pins & MC6847_AG) && addr < 0x800) // character mode
    {
        uint8_t attr = sys->vram[addr + 0x800];
        if (attr & ATTR_CSS)
            pins |= MC6847_CSS;
        else
            pins &= ~MC6847_CSS;
        if (attr & ATTR_INV)
            pins |= MC6847_INV;
        else
            pins &= ~MC6847_INV;
        if (attr & ATTR_EXT)
            pins |= MC6847_INTEXT;
        else
            pins &= ~MC6847_INTEXT;
        if (attr & ATTR_SEM)
            pins |= MC6847_AS;
        else
            pins &= ~MC6847_AS;
    }
    return pins;
}

static void _spc1000_init_keymap(spc1000_t* sys) {
    /*  setup the keyboard matrix
        the spc1000 has a 10x8 keyboard matrix, where the
        entire line 6 is for the Ctrl key, and the entire
        line 7 is the Shift key
    */
    kbd_init(&sys->kbd, 1);
    /* shift key is entire line 7 */
    const int shift = (1<<0); kbd_register_modifier(&sys->kbd, 0, 0, 1);
    /* ctrl key is entire line 6 */
    //const int ctrl = (1<<1); kbd_register_modifier(&sys->kbd, 2, 0, 2);
    /* alpha-numeric keys */
    const char* keymap = 
        /* no shift */
        "        "/**/"~   caq1"/**/"  z]vsw2"/* */"   [bde3"/**/"   \\nfr4"/**/"    mgt5"/**/"  @x,hy6"/**/"   p.ju7"/**/"   :/ki8"/**/"  -0;lo9"
        /* shift */
        "        "/**/"    CAQ!"/**/"  Z}VSW\""/**/"   {BDE#"/**/"   |NFR$"/* */"    MGT%"/**/"  'X<HY^"/**/"   P>JU&"/**/"   ;?KI*"/**/"  _)'LO(";
    for (int layer = 0; layer < 2; layer++) {
        for (int column = 0; column < 10; column++) {
            for (int line = 0; line < 8; line++) {
                int c = keymap[layer*80 + line + column*8];
                if (c != 0x20) {
                    kbd_register_key(&sys->kbd, c, column, line, layer?shift:0);
                }
            }
        }
    }
    /* special keys */
    kbd_register_key(&sys->kbd, 0x20, 1, 2, 0);         /* space */
    kbd_register_key(&sys->kbd, 0x0D, 1, 3, 0);         /* return/enter */
    kbd_register_key(&sys->kbd, 0x0C, 3, 0, 0);         /* backspace */
    kbd_register_key(&sys->kbd, 0x08, 5, 2, 0);         /* key left */
    kbd_register_key(&sys->kbd, 0x09, 4, 2, 0);         /* key right */
    kbd_register_key(&sys->kbd, 0x0A, 8, 2, 0);         /* key down */
    kbd_register_key(&sys->kbd, 0x0B, 7, 2, 0);         /* key up */
    kbd_register_key(&sys->kbd, 0x0F, 0, 2, 0);			/* ctrl */
	kbd_register_key(&sys->kbd, 0xF1, 5, 1, 0);			/* F1 */
	kbd_register_key(&sys->kbd, 0xF2, 6, 1, 0);			/* F2 */
	kbd_register_key(&sys->kbd, 0xF3, 7, 1, 0);			/* F3 */
	kbd_register_key(&sys->kbd, 0xF4, 8, 1, 0);			/* F4 */
	kbd_register_key(&sys->kbd, 0xF5, 9, 1, 0);			/* F5 */
	kbd_register_key(&sys->kbd, 0xF6, 0, 4, 0);			/* Break */
	kbd_register_key(&sys->kbd, 0x0E, 0, 1, 0);			/* Shift */
	kbd_register_key(&sys->kbd, 0xF7, 2, 0, 0);			/* Caps */
	kbd_register_key(&sys->kbd, 0xF8, 0, 6, 0);			/* Graph (ALT) */


#if 0    
    kbd_register_key(&sys->kbd, 0x01, 4, 1, 0);         /* backspace */
    kbd_register_key(&sys->kbd, 0x07, 0, 3, ctrl);      /* Ctrl+G: bleep */
    kbd_register_key(&sys->kbd, 0x08, 3, 0, shift);     /* key left */
    kbd_register_key(&sys->kbd, 0x09, 3, 0, 0);         /* key right */
    kbd_register_key(&sys->kbd, 0x0A, 2, 0, shift);     /* key down */
    kbd_register_key(&sys->kbd, 0x0B, 2, 0, 0);         /* key up */
    kbd_register_key(&sys->kbd, 0x0C, 5, 4, ctrl);      /* Ctrl+L clear screen */
    kbd_register_key(&sys->kbd, 0x0E, 3, 4, ctrl);      /* Ctrl+N page mode on */
    kbd_register_key(&sys->kbd, 0x0F, 2, 4, ctrl);      /* Ctrl+O page mode off */
    kbd_register_key(&sys->kbd, 0x15, 6, 5, ctrl);      /* Ctrl+U end screen */
    kbd_register_key(&sys->kbd, 0x18, 3, 5, ctrl);      /* Ctrl+X cancel */
    kbd_register_key(&sys->kbd, 0x1B, 0, 5, 0);         /* escape */
#endif    
}

static uint32_t _spc1000_xorshift32(uint32_t x) {
    x ^= x<<13;
    x ^= x>>17;
    x ^= x<<5;
    return x;
}

static void _spc1000_init_memorymap(spc1000_t* sys) {
    mem_init(&sys->mem);

    /* fill memory with random junk */
    uint32_t r = 0x6D98302B;
    for (int i = 0; i < (int)sizeof(sys->ram);) {
        r = _spc1000_xorshift32(r);
        sys->ram[i++] = r;
        sys->ram[i++] = (r>>8);
        sys->ram[i++] = (r>>16);
        sys->ram[i++] = (r>>24);
    }
    /* 64 KB RAM */
    mem_map_ram(&sys->mem, 0, 0x0000, 0x10000, sys->ram);
    mem_map_ram(&sys->mem, 1, 0x0000, 0x2000, sys->vram);
    /* 32 KB ROMs from 0x000 */
    //mem_map_rom(&sys->mem, 1, 0x0000, 0x8000, sys->rom);
}

/*=== FILE LOADING ===========================================================*/
/* spc1000 TAP / ATM header (https://github.com/hoglet67/spc1000ulator/blob/master/docs/spc1000mmc2.txt ) */
typedef struct {
    uint8_t name[16];
    uint16_t load_addr;
    uint16_t exec_addr;
    uint16_t length;
} _spc1000_tap_header;

bool spc1000_insert_tape(spc1000_t* sys, const uint8_t* ptr, int num_bytes) {
    CHIPS_ASSERT(sys && sys->valid);
    CHIPS_ASSERT(ptr);
    spc1000_remove_tape(sys);
    /* check for valid size */
    if ((num_bytes < (int)sizeof(_spc1000_tap_header)) || (num_bytes > SPC1K_MAX_TAPE_SIZE)) {
        return false;
    }
    memcpy(sys->tape_buf, ptr, num_bytes);
    sys->tape_pos = 0;
    sys->tape_size = num_bytes;
    return true;
}


bool spc1000_tapeload(spc1000_t* sys, const uint8_t* ptr, int num_bytes) {
    sys->tape_size = num_bytes;
    sys->tape_pos = 0;
    memcpy(sys->tape_buf, ptr, num_bytes);
    return true;
}

void spc1000_remove_tape(spc1000_t* sys) {
    CHIPS_ASSERT(sys && sys->valid);
    sys->tape_pos = 0;
    sys->tape_size = 0;
}

/*
    trapped OSLOAD function, load ATM block in a TAP file:
      https://github.com/hoglet67/spc1000ulator/blob/master/docs/spc1000mmc2.tx
    from: http://ladybug.xs4all.nl/arlet/fpga/6502/kernel.di
      OSLOAD Load File subroutine
       --------------------------
     - Entry: 0,X = LSB File name string address
              1,X = MSB File name string address
              2,X = LSB Data dump start address
              3,X = MSB Data dump start address
              4,X : If bit 7 is clear, then the file's own start address is
                    to be used
              #DD = FLOAD flag - bit 7 is set if in FLOAD mod
     - Uses:  #C9 = LSB File name string address
              #CA = MSB File name string address
              #CB = LSB Data dump start address
              #CC = MSB Data dump start address
              #CD = load flag - if bit 7 is set, then the load address at
                    (#CB) is to be used instead of the file's load address
              #D0 = MSB Current block number
              #D1 = LSB Current block numbe
     - Header format: <*>                      )
                      <*>                      )
                      <*>                      )
                      <*>                      ) Header preamble
                      <Filename>               ) Name is 1 to 13 bytes long
                      <Status Flag>            ) Bit 7 clear if last block
                                               ) Bit 6 clear to skip block
                                               ) Bit 5 clear if first block
                      <LSB block number>
                      <MSB block number>       ) Always zero
                      <Bytes in block>
                      <MSB run address>
                      <LSB run address>
                      <MSB block load address>
                      <LSB block load address
     - Data format:   <....data....>           ) 1 to #FF bytes
                      <Checksum>               ) LSB sum of all data byte
*/
void _spc1000_osload(spc1000_t* sys) {
    bool success = false;

    /* tape inserted? */
    uint16_t exec_addr = 0;
    if ((sys->tape_size > 0) && (sys->tape_pos < sys->tape_size)) {
        /* read next tape chunk */
        if ((int)(sys->tape_pos + sizeof(_spc1000_tap_header)) < sys->tape_size) {
            const _spc1000_tap_header* hdr = (const _spc1000_tap_header*) &sys->tape_buf[sys->tape_pos];
            sys->tape_pos += sizeof(_spc1000_tap_header);
            exec_addr = hdr->exec_addr;
            uint16_t addr = hdr->load_addr;
            /* override file load address? */
            if (mem_rd(&sys->mem, 0xCD) & 0x80) {
                addr = mem_rd16(&sys->mem, 0xCB);
            }
            if ((sys->tape_pos + hdr->length) <= sys->tape_size) {
                for (int i = 0; i < hdr->length; i++) {
                    mem_wr(&sys->mem, addr++, sys->tape_buf[sys->tape_pos++]);
                }
                success = true;
            }
        }
    }
    /* if tape at end, remove tape */
    if (sys->tape_pos >= sys->tape_size) {
        spc1000_remove_tape(sys);
    }
}


#endif /* CHIPS_IMPL */
