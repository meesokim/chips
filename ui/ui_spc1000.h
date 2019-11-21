#pragma once
/*#
    # ui_spc1000.h

    Integrated debugging UI for spc1000.h

    Do this:
    ~~~C
    #define CHIPS_IMPL
    ~~~
    before you include this file in *one* C++ file to create the 
    implementation.

    Optionally provide the following macros with your own implementation
    
    ~~~C
    CHIPS_ASSERT(c)
    ~~~
        your own assert macro (default: assert(c))

    Include the following headers (and their depenencies) before including
    ui_spc1000.h both for the declaration and implementation.

    - spc1000.h
    - mem.h
    - ui_chip.h
    - ui_util.h
    - ui_z80.h
    - ui_ay38910.h
    - ui_audio.h
    - ui_kbd.h
    - ui_dasm.h
    - ui_dbg.h
    - ui_memedit.h
    - ui_memmap.h

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
#*/
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* general callback type for rebooting to different configs */
typedef void (*ui_spc1000_boot_t)(spc1000_t* sys, spc1000_type_t type);

typedef struct {
    spc1000_t* spc1000;
    ui_spc1000_boot_t boot_cb; /* user-provided callback to reboot to different config */
    ui_dbg_create_texture_t create_texture_cb;      /* texture creation callback for ui_dbg_t */
    ui_dbg_update_texture_t update_texture_cb;      /* texture update callback for ui_dbg_t */
    ui_dbg_destroy_texture_t destroy_texture_cb;    /* texture destruction callback for ui_dbg_t */
    ui_dbg_keydesc_t dbg_keys;          /* user-defined hotkeys for ui_dbg_t */
} ui_spc1000_desc_t;

typedef struct {
    spc1000_t* spc1000;
    ui_spc1000_boot_t boot_cb;
    ui_z80_t cpu;
    ui_ay38910_t ay;
    ui_audio_t audio;
    ui_kbd_t kbd;
    ui_memmap_t memmap;
    ui_memedit_t memedit[4];
    ui_dasm_t dasm[4];
    ui_dbg_t dbg;
} ui_spc1000_t;

void ui_spc1000_init(ui_spc1000_t* ui, const ui_spc1000_desc_t* desc);
void ui_spc1000_discard(ui_spc1000_t* ui);
void ui_spc1000_draw(ui_spc1000_t* ui, double time_ms);
bool ui_spc1000_before_exec(ui_spc1000_t* ui);
void ui_spc1000_after_exec(ui_spc1000_t* ui);

#ifdef __cplusplus
} /* extern "C" */
#endif

/*-- IMPLEMENTATION (include in C++ source) ----------------------------------*/
#ifdef CHIPS_IMPL
#ifndef __cplusplus
#error "implementation must be compiled as C++"
#endif
#include <string.h> /* memset */
#ifndef CHIPS_ASSERT
    #include <assert.h>
    #define CHIPS_ASSERT(c) assert(c)
#endif
#ifdef __clang__
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wmissing-field-initializers"
#endif

static void _ui_spc1000_draw_menu(ui_spc1000_t* ui, uint64_t time_ms) {
    CHIPS_ASSERT(ui && ui->spc1000 && ui->boot_cb);
    if (ImGui::BeginMainMenuBar()) {
        if (ImGui::BeginMenu("System")) {
            if (ImGui::MenuItem("Reset")) {
                spc1000_reset(ui->spc1000);
                ui_dbg_reset(&ui->dbg);
            }
            if (ImGui::MenuItem("SPC1000", 0, (ui->spc1000->type == SPC1000))) {
                ui->boot_cb(ui->spc1000, SPC1000);
                ui_dbg_reboot(&ui->dbg);
            }
            if (ImGui::MenuItem("SPC1000A", 0, (ui->spc1000->type == SPC1000A))) {
                ui->boot_cb(ui->spc1000, SPC1000A);
                ui_dbg_reboot(&ui->dbg);
            }
            if (ImGui::BeginMenu("Joystick")) {
                if (ImGui::MenuItem("None", 0, (ui->spc1000->joystick_type == SPC1K_JOYSTICKTYPE_NONE))) {
                    ui->spc1000->joystick_type =SPC1K_JOYSTICKTYPE_NONE;
                }
                if (ImGui::MenuItem("Kempston", 0, (ui->spc1000->joystick_type == SPC1K_JOYSTICKTYPE_MMC))) {
                    ui->spc1000->joystick_type = SPC1K_JOYSTICKTYPE_MMC;
                }
                ImGui::EndMenu();
            }
            ImGui::EndMenu();
        }
        if (ImGui::BeginMenu("Hardware")) {
            ImGui::MenuItem("Memory Map", 0, &ui->memmap.open);
            ImGui::MenuItem("Keyboard Matrix", 0, &ui->kbd.open);
            ImGui::MenuItem("Audio Output", 0, &ui->audio.open);
            ImGui::MenuItem("Z80 CPU", 0, &ui->cpu.open);
            ImGui::MenuItem("AY-3-8912", 0, &ui->ay.open);
            ImGui::EndMenu();
        }
        if (ImGui::BeginMenu("Debug")) {
            ImGui::MenuItem("CPU Debugger", 0, &ui->dbg.ui.open);
            ImGui::MenuItem("Breakpoints", 0, &ui->dbg.ui.show_breakpoints);
            ImGui::MenuItem("Memory Heatmap", 0, &ui->dbg.ui.show_heatmap);
            if (ImGui::BeginMenu("Memory Editor")) {
                ImGui::MenuItem("RAM", 0, &ui->memedit[0].open);
                ImGui::MenuItem("VRAM", 0, &ui->memedit[1].open);
                ImGui::EndMenu();
            }
            if (ImGui::BeginMenu("Disassembler")) {
                ImGui::MenuItem("RAM", 0, &ui->dasm[0].open);
                ImGui::EndMenu();
            }
            ImGui::EndMenu();
        }
        ui_util_options_menu_time(time_ms, ui->dbg.dbg.stopped);
        ImGui::EndMainMenuBar();
    }
    
}

static void _ui_spc1000_update_memmap(ui_spc1000_t* ui) {
    CHIPS_ASSERT(ui && ui->spc1000);
    ui_memmap_reset(&ui->memmap);
    if (SPC1000 == ui->spc1000->type) {
        ui_memmap_layer(&ui->memmap, "System");
        ui_memmap_region(&ui->memmap, "RAM", 0x0000, 0x10000, true);
    }
}

static uint8_t* _ui_spc1000_memptr(spc1000_t* spc1000, int layer, uint16_t addr) {
    if (0 == layer) {
        return &spc1000->ram[addr];
    }
    else if (1 == layer) {
        if (addr < 0x2000)
            return &spc1000->vram[addr];
    }
    /* fallthrough: unmapped memory */
    return 0;
}

static uint8_t _ui_spc1000_mem_read(int layer, uint16_t addr, void* user_data) {
    CHIPS_ASSERT(user_data);
    spc1000_t* spc1000 = (spc1000_t*) user_data;
        /* CPU visible layer */
    if (layer == 1)
        return spc1000->vram[addr];
    return spc1000->ram[addr];
}

static void _ui_spc1000_mem_write(int layer, uint16_t addr, uint8_t data, void* user_data) {
    CHIPS_ASSERT(user_data);
    spc1000_t* spc1000 = (spc1000_t*) user_data;
    if (layer == 0) {
        mem_wr(&spc1000->mem, addr, data);
    } else if (layer == 1) {
        spc1000->vram[addr] = data;
    };
}

static const ui_chip_pin_t _ui_spc1000_cpu_pins[] = {
    { "D0",     0,      Z80_D0 },
    { "D1",     1,      Z80_D1 },
    { "D2",     2,      Z80_D2 },
    { "D3",     3,      Z80_D3 },
    { "D4",     4,      Z80_D4 },
    { "D5",     5,      Z80_D5 },
    { "D6",     6,      Z80_D6 },
    { "D7",     7,      Z80_D7 },
    { "M1",     9,      Z80_M1 },
    { "MREQ",   10,     Z80_MREQ },
    { "IORQ",   11,     Z80_IORQ },
    { "RD",     12,     Z80_RD },
    { "WR",     13,     Z80_WR },
    { "HALT",   14,     Z80_HALT },
    { "INT",    15,     Z80_INT },
    { "NMI",    16,     Z80_NMI },
    { "WAIT",   17,     Z80_WAIT_MASK },
    { "A0",     18,     Z80_A0 },
    { "A1",     19,     Z80_A1 },
    { "A2",     20,     Z80_A2 },
    { "A3",     21,     Z80_A3 },
    { "A4",     22,     Z80_A4 },
    { "A5",     23,     Z80_A5 },
    { "A6",     24,     Z80_A6 },
    { "A7",     25,     Z80_A7 },
    { "A8",     26,     Z80_A8 },
    { "A9",     27,     Z80_A9 },
    { "A10",    28,     Z80_A10 },
    { "A11",    29,     Z80_A11 },
    { "A12",    30,     Z80_A12 },
    { "A13",    31,     Z80_A13 },
    { "A14",    32,     Z80_A14 },
    { "A15",    33,     Z80_A15 },
};

static const ui_chip_pin_t _ui_spc1000_ay_pins[] = {
    { "DA0",  0, AY38910_DA0 },
    { "DA1",  1, AY38910_DA1 },
    { "DA2",  2, AY38910_DA2 },
    { "DA3",  3, AY38910_DA3 },
    { "DA4",  4, AY38910_DA4 },
    { "DA5",  5, AY38910_DA5 },
    { "DA6",  6, AY38910_DA6 },
    { "DA7",  7, AY38910_DA7 },
    { "BDIR", 9, AY38910_BDIR },
    { "BC1",  10, AY38910_BC1 },
    { "IOA0", 11, AY38910_IOA0 },
    { "IOA1", 12, AY38910_IOA1 },
    { "IOA2", 13, AY38910_IOA2 },
    { "IOA3", 14, AY38910_IOA3 },
    { "IOA4", 15, AY38910_IOA4 },
    { "IOA5", 16, AY38910_IOA5 },
    { "IOA6", 17, AY38910_IOA6 },
    { "IOA7", 18, AY38910_IOA7 },
};

void ui_spc1000_init(ui_spc1000_t* ui, const ui_spc1000_desc_t* ui_desc) {
    CHIPS_ASSERT(ui && ui_desc);
    CHIPS_ASSERT(ui_desc->spc1000);
    CHIPS_ASSERT(ui_desc->boot_cb);
    ui->spc1000 = ui_desc->spc1000;
    ui->boot_cb = ui_desc->boot_cb;
    int x = 20, y = 20, dx = 10, dy = 10;
    {
        ui_dbg_desc_t desc = {0};
        desc.title = "CPU Debugger";
        desc.x = x;
        desc.y = y;
        desc.z80 = &ui->spc1000->cpu;
        desc.read_cb = _ui_spc1000_mem_read;
        desc.create_texture_cb = ui_desc->create_texture_cb;
        desc.update_texture_cb = ui_desc->update_texture_cb;
        desc.destroy_texture_cb = ui_desc->destroy_texture_cb;
        desc.keys = ui_desc->dbg_keys;
        desc.user_data = ui->spc1000;
        ui_dbg_init(&ui->dbg, &desc);
    }
    x += dx; y += dy;
    {
        ui_z80_desc_t desc = {0};
        desc.title = "Z80 CPU";
        desc.cpu = &ui->spc1000->cpu;
        desc.x = x;
        desc.y = y;
        UI_CHIP_INIT_DESC(&desc.chip_desc, "Z80\nCPU", 36, _ui_spc1000_cpu_pins);
        ui_z80_init(&ui->cpu, &desc);
    }
    x += dx; y += dy;
    {
        ui_ay38910_desc_t desc = {0};
        desc.title = "AY-3-8912";
        desc.ay = &ui->spc1000->ay;
        desc.x = x;
        desc.y = y;
        UI_CHIP_INIT_DESC(&desc.chip_desc, "8912", 22, _ui_spc1000_ay_pins);
        ui_ay38910_init(&ui->ay, &desc);
    }
    x += dx; y += dy;
    {
        ui_kbd_desc_t desc = {0};
        desc.title = "Keyboard Matrix";
        desc.kbd = &ui->spc1000->kbd;
        desc.layers[0] = "None";
        desc.layers[1] = "Shift";
        desc.layers[2] = "Sym Shift";
        desc.x = x;
        desc.y = y;
        ui_kbd_init(&ui->kbd, &desc);
    }
    x += dx; y += dy;
    {
        ui_audio_desc_t desc = {0};
        desc.title = "Audio Output";
        desc.sample_buffer = ui->spc1000->sample_buffer;
        desc.num_samples = ui->spc1000->num_samples;
        desc.x = x;
        desc.y = y;
        ui_audio_init(&ui->audio, &desc);
    }
    x += dx; y += dy;
    {
        ui_memedit_desc_t desc = {0};
        desc.layers[0] = "CPU Mapped";
        desc.layers[1] = "Layer 0";
        desc.layers[2] = "Layer 1";
        desc.layers[3] = "Layer 2";
        desc.layers[4] = "Layer 3";
        desc.layers[5] = "Layer 4";
        desc.layers[6] = "Layer 5";
        desc.layers[7] = "Layer 6";
        desc.read_cb = _ui_spc1000_mem_read;
        desc.write_cb = _ui_spc1000_mem_write;
        desc.user_data = ui->spc1000;
        static const char* titles[] = { "Memory Editor #1", "Memory Editor #2", "Memory Editor #3", "Memory Editor #4" };
        for (int i = 0; i < 2; i++) {
            desc.title = titles[i]; desc.x = x; desc.y = y;
            ui_memedit_init(&ui->memedit[i], &desc);
            x += dx; y += dy;
        }
    }
    {
        ui_memmap_desc_t desc = {0};
        desc.title = "Memory Map";
        desc.x = x;
        desc.y = y;
        ui_memmap_init(&ui->memmap, &desc);
    }
    x += dx; y += dy;
    {
        ui_dasm_desc_t desc = {0};
        desc.layers[0] = "CPU Mapped";
        desc.layers[1] = "Layer 0";
        desc.layers[2] = "Layer 1";
        desc.layers[3] = "Layer 2";
        desc.layers[4] = "Layer 3";
        desc.layers[5] = "Layer 4";
        desc.layers[6] = "Layer 5";
        desc.layers[7] = "Layer 6";
        desc.cpu_type = UI_DASM_CPUTYPE_Z80;
        desc.start_addr = 0x0000;
        desc.read_cb = _ui_spc1000_mem_read;
        desc.user_data = ui->spc1000;
        static const char* titles[4] = { "Disassembler #1", "Disassembler #2", "Disassembler #2", "Dissassembler #3" };
        for (int i = 0; i < 4; i++) {
            desc.title = titles[i]; desc.x = x; desc.y = y;
            ui_dasm_init(&ui->dasm[i], &desc);
            x += dx; y += dy;
        }
    }
}

void ui_spc1000_discard(ui_spc1000_t* ui) {
    CHIPS_ASSERT(ui && ui->spc1000);
    ui->spc1000 = 0;
    ui_z80_discard(&ui->cpu);
    ui_ay38910_discard(&ui->ay);
    ui_audio_discard(&ui->audio);
    ui_kbd_discard(&ui->kbd);
    ui_memmap_discard(&ui->memmap);
    for (int i = 0; i < 2; i++) {
        ui_memedit_discard(&ui->memedit[i]);
        ui_dasm_discard(&ui->dasm[i]);
    }
    ui_dbg_discard(&ui->dbg);
}

void ui_spc1000_draw(ui_spc1000_t* ui, double time_ms) {
    CHIPS_ASSERT(ui && ui->spc1000);
    //_ui_spc1000_draw_menu(ui, ui->spc1000->tick_count);
    if (ui->memmap.open) {
        _ui_spc1000_update_memmap(ui);
    }
    ui_audio_draw(&ui->audio, ui->spc1000->sample_pos);
    ui_z80_draw(&ui->cpu);
    ui_ay38910_draw(&ui->ay);
    ui_kbd_draw(&ui->kbd);
    ui_memmap_draw(&ui->memmap);
    for (int i = 0; i < 2; i++) {
        ui_memedit_draw(&ui->memedit[i]);
        ui_dasm_draw(&ui->dasm[i]);
    }
    ui_dbg_draw(&ui->dbg);
    if (ui->spc1000->tapeMotor)
    {
        bool g_bMenuOpen = false;
        int w = (100 * ui->spc1000->tape_pos) / ui->spc1000->tape_size;
        ImVec2 xy(0,22);// = ImGui::GetItemRectMin();
        ImGui::Begin("A", &g_bMenuOpen, ImVec2((float)sapp_width()*sapp_dpi_scale(),20), 0.f, ImGuiWindowFlags_AlwaysUseWindowPadding | ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_NoNav | ImGuiWindowFlags_AlwaysUseWindowPadding);
        ImGuiStyle& style = ImGui::GetStyle();
        style.WindowBorderSize = 0.0f;  
        ImGui::SetWindowFocus("top"); 
        ImGui::GetWindowDrawList()->AddRectFilled(ImVec2(0,25), ImVec2((float) (sapp_window_width() + xy.x), 60), IM_COL32(0,0,180,255));
        ImGui::GetWindowDrawList()->AddRectFilled(ImVec2(0,25), ImVec2((float) (w * sapp_width() / 100 + xy.x), 60), IM_COL32(255,0,0,255));//ImVec2(10,10), ImVec2(320,20), IM_COL32(0,255,255,55));
        ImGui::SetWindowPos(xy);
        ImGui::SetWindowFontScale(1.2f);
        ImGui::Text("Tape: %3d%%", w);
        ImGui::End();
    }
}

bool ui_spc1000_before_exec(ui_spc1000_t* ui) {
    CHIPS_ASSERT(ui && ui->spc1000);
    return ui_dbg_before_exec(&ui->dbg);
}

void ui_spc1000_after_exec(ui_spc1000_t* ui) {
    CHIPS_ASSERT(ui && ui->spc1000);
    ui_dbg_after_exec(&ui->dbg);
}

#ifdef __clang__
#pragma clang diagnostic pop
#endif
#endif /* CHIPS_IMPL */
