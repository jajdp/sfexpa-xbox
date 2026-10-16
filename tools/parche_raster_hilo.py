# -*- coding: utf-8 -*-
# Rasterizador por software rápido y pasada ancha (16:9) en un segundo hilo, con los MISMOS píxeles, en
# psxrecomp/runtime/src/: gpu_sw_renderer.c, gpu.c y main.cpp. Parte del gpu_sw_renderer.c ORIGINAL.
# Motivo (medido en la xbox series cuarto, 2026-10-03, con la demo del juego y el registro de fases): en 16:9 las
# peleas iban a 54-55 FPS y en 4:3 a 60, porque el modo ancho dibuja cada primitiva dos veces (la VRAM fiel y la
# superficie ancha) y en la consola el dibujo es por software; con el rasterizador rápido, 56-59, y el dibujo seguía
# siendo el 26-32 % del cuadro.
#  1. Caminos rápidos (sin filtrado bilineal): el estado de dibujo se toma una vez por primitiva (RState), el texel y
#     el píxel van en línea sin las comprobaciones que el recorte ya garantiza, la división por píxel pasa a
#     k * (1 / span) en doble (da el mismo float: demostrado en el comentario del código) y los rectángulos escalados
#     usan un DDA entero exacto en vez de la división de 64 bits por píxel.
#  2. La pasada ancha va a un segundo hilo, en orden, por un anillo de órdenes completas (estado, destino y
#     coordenadas ya resueltas). El hilo solo lee la VRAM y solo escribe superficies anchas. Se espera a que vacíe el
#     anillo antes de presentar o volcar una superficie ancha y antes de cualquier escritura en línea en una de ellas.
#     Antes de escribir la VRAM (cada dibujo en su área de dibujo, rellenos, copias, cargas CPU->VRAM —en gpu.c, al
#     empezar—, el reinicio de la GPU y la carga de estados) se espera solo a las órdenes pendientes que leen texeles o
#     paleta en esa zona: una lista de hasta 16 rectángulos de lectura, cada uno con el número de su última orden.
#     Solo en Windows y a escala 1 sin bilineal; si no, la pasada sigue en línea, como antes.
#  3. La línea [FPS] añade las órdenes encoladas y las esperas de cada segundo («wide worker N cmds M waits»), para
#     saber si el hilo trabaja en paralelo o se sincroniza demasiado.
# Comprobado (2026-10-03) en un banco que dibuja con el original y con este, con las mismas
# operaciones al azar (5 semillas x 100 000; escala 1 y 2; con y sin bilineal; la variante con hilo tres veces por
# semilla), dan las mismas huellas en las 40 comparaciones; un cuadro de pelea sintético baja de 11,7 a 4,5 ms en el
# PC. En la xbox series cuarto (0.2.9.3, demo en 16:9): 60 FPS en la pelea pesada (antes 56-59), el dibujo baja del
# 25-30 % al 9-16 % del cuadro, ~82 000 órdenes por segundo al hilo y 0 esperas.
# Los comentarios del código van en inglés, como el resto del runtime. Todo o nada; atómico; conserva el fin de línea.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parchear  # noqa: E402

SOLO_SW = '--solo-renderer' in sys.argv          # para el banco: solo gpu_sw_renderer.c (ni gpu.c ni main.cpp)
# Con --solo-renderer el argumento es la carpeta tal cual (el banco de pruebas trabaja sobre
# una copia de gpu_sw_renderer.c, que no es un arbol del juego); si no, es la raiz del arbol.
if SOLO_SW:
    _POS = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not _POS:
        sys.exit('uso: parche_raster_hilo.py <carpeta con gpu_sw_renderer.c> --solo-renderer')
    R = os.path.abspath(_POS[0])
else:
    R = parchear.runtime(parchear.raiz(), 'src')
MARCA = 'Recompilaciones (2026-10-03): fast nearest-filter rasterizer + native-wide worker'

BLOQUE = r'''/* ==== ''' + MARCA + r''' ====
 * (1) Fast paths (nearest filtering). The per-pixel texel_fetch/put_* calls re-read the draw
 *     state (mask bits, semi-transparency, texture window, texpage/CLUT decode) on every pixel —
 *     MSVC cannot keep globals in registers across the 16-bit stores — and re-check bounds the
 *     span clipping already guarantees. fastr_* take that state once per primitive (RState) and
 *     inline the fetch/write. Per-row math is unchanged; per-pixel interpolation is bit-identical:
 *     (float)k / (float)span becomes k * (1/span) in double, which rounds to the same float for
 *     0 <= k < 2^24 and span < 2^27 (the exact quotient is never within 2^-51 of a float rounding
 *     midpoint; the double product errs by < 2^-52). Scaled rects use an exact integer DDA for the
 *     per-pixel 64-bit division. Bilinear filtering keeps the original code.
 * (2) Native-wide worker. Native-wide rasterizes every framebuffer primitive twice (canonical VRAM
 *     + the wide surface); on the Xbox (software renderer) that held 3D fights below 60 fps in
 *     16:9. The wide pass runs on a second thread, in order, from a ring of self-contained commands
 *     (state snapshot, resolved target, final coordinates). It only READS canonical VRAM and only
 *     WRITES wide surfaces. Drain points: before presenting/dumping a wide surface; before a
 *     canonical VRAM write overlapping texels/CLUTs pending commands will read (each canonical draw
 *     area, fills, copies, CPU->VRAM uploads — gpu.c, at upload start —, resets, savestate loads);
 *     before any inline wide-surface write; before freeing surfaces. Windows only; at supersampling
 *     > 1 or with bilinear the pass stays inline. Verified bit-identical (randomized harness). */

typedef struct {
    int mask_check, mask_set, semi, mode;
    int mod_r, mod_g, mod_b, raw;
    int tw_mask_x, tw_mask_y, tw_off_x, tw_off_y;
} RState;

static inline void rstate_globals(RState *s) {
    s->mask_check = g_mask_check_bit; s->mask_set = g_mask_set_bit;
    s->semi = g_semi_trans_enabled;   s->mode = g_semi_trans_mode;
    s->mod_r = g_mod_r; s->mod_g = g_mod_g; s->mod_b = g_mod_b; s->raw = g_raw_texture;
    s->tw_mask_x = g_tw_mask_x; s->tw_mask_y = g_tw_mask_y;
    s->tw_off_x = g_tw_off_x;   s->tw_off_y = g_tw_off_y;
}

typedef struct {
    const uint16_t *vram;
    int tpx, tpy, depth, clut_x, clut_row;
    int u_and, u_or, v_and, v_or;           /* texture window, always applied (identity when off) */
} FastTex;

static inline void fast_tex_init(FastTex *f, const RState *s, uint16_t texpage,
                                 uint16_t clut_x, uint16_t clut_y) {
    f->vram     = g_vram;
    f->tpx      = (texpage & 0xF) * 64;
    f->tpy      = ((texpage >> 4) & 1) * 256;
    f->depth    = (texpage >> 7) & 3;
    f->clut_x   = clut_x;
    f->clut_row = (clut_y & (VRAM_HEIGHT - 1)) * VRAM_WIDTH;
    f->u_and = ~(s->tw_mask_x * 8); f->u_or = (s->tw_off_x & s->tw_mask_x) * 8;
    f->v_and = ~(s->tw_mask_y * 8); f->v_or = (s->tw_off_y & s->tw_mask_y) * 8;
}

/* Same result as texel_fetch(u, v, ...) for u, v in 0..255. */
static inline uint16_t fast_tex_fetch(const FastTex *f, int u, int v) {
    u = (u & f->u_and) | f->u_or;
    v = (v & f->v_and) | f->v_or;
    const int row = ((f->tpy + v) & (VRAM_HEIGHT - 1)) * VRAM_WIDTH;
    switch (f->depth) {
    case 0: {
        const uint16_t w = f->vram[row + ((f->tpx + (u >> 2)) & (VRAM_WIDTH - 1))];
        return f->vram[f->clut_row + ((f->clut_x + ((w >> ((u & 3) * 4)) & 0xF)) & (VRAM_WIDTH - 1))];
    }
    case 1: {
        const uint16_t w = f->vram[row + ((f->tpx + (u >> 1)) & (VRAM_WIDTH - 1))];
        return f->vram[f->clut_row + ((f->clut_x + ((w >> ((u & 1) * 8)) & 0xFF)) & (VRAM_WIDTH - 1))];
    }
    default:
        return f->vram[row + ((f->tpx + u) & (VRAM_WIDTH - 1))];
    }
}

/* put_textured() without the bounds checks (the caller clips). */
static inline void fast_put_textured(const RState *s, uint16_t *dst, uint16_t texel,
                                     int mod_r, int mod_g, int mod_b, int raw_texture) {
    if (texel == 0x0000) return;
    if (s->mask_check && (*dst & 0x8000)) return;
    uint16_t color;
    if (!raw_texture) {
        int tr = (texel >>  0) & 0x1F;
        int tg = (texel >>  5) & 0x1F;
        int tb = (texel >> 10) & 0x1F;
        int r = (tr * mod_r) >> 4; if (r > 31) r = 31;
        int g = (tg * mod_g) >> 4; if (g > 31) g = 31;
        int b = (tb * mod_b) >> 4; if (b > 31) b = 31;
        color = (uint16_t)(r | (g << 5) | (b << 10));
    } else {
        color = texel & 0x7FFF;
    }
    if (s->semi && (texel & 0x8000)) color = blend_pixels(*dst, color, s->mode);
    if (s->mask_set) color |= 0x8000;
    *dst = color;
}

/* put_opaque() without the bounds checks (the caller clips). */
static inline void fast_put_opaque(const RState *s, uint16_t *dst, uint16_t color) {
    if (s->mask_check && (*dst & 0x8000)) return;
    if (s->semi) color = blend_pixels(*dst, color, s->mode);
    if (s->mask_set) color |= 0x8000;
    *dst = color;
}

/* A row of put_opaque(t, x, y, color) for x in [sx, ex), sx/ex already clipped to the target's
 * clip rect: applies the remaining put_opaque bounds (buffer edges). */
static inline void fast_span_opaque(const RTarget *t, const RState *s, int y, int sx, int ex,
                                    uint16_t color) {
    if (y < 0 || y >= t->h) return;
    if (sx < 0) sx = 0;
    if (ex > t->w) ex = t->w;
    uint16_t *row = t->buf + (size_t)y * t->w;
    if (!s->mask_check && !s->semi) {
        const uint16_t c = s->mask_set ? (uint16_t)(color | 0x8000) : color;
        for (int x = sx; x < ex; x++) row[x] = c;
    } else {
        for (int x = sx; x < ex; x++) fast_put_opaque(s, row + x, color);
    }
}

/* put_opaque(t, x, y, color) with explicit state (lines). */
static inline void fast_put_opaque_checked(const RTarget *t, const RState *s, int x, int y,
                                           uint16_t color) {
    if (x < 0 || x >= t->w || y < 0 || y >= t->h) return;
    if (x < t->cx1 || x > t->cx2 || y < t->cy1 || y > t->cy2) return;
    fast_put_opaque(s, t->buf + (size_t)y * t->w + x, color);
}

static void fastr_flat_triangle(const RTarget *t, const RState *st,
                                int x0, int y0, int x1, int y1,
                                int x2, int y2, uint16_t color) {
    if (y0 > y1) { int tt; tt=x0; x0=x1; x1=tt; tt=y0; y0=y1; y1=tt; }
    if (y0 > y2) { int tt; tt=x0; x0=x2; x2=tt; tt=y0; y0=y2; y2=tt; }
    if (y1 > y2) { int tt; tt=x1; x1=x2; x2=tt; tt=y1; y1=y2; y2=tt; }

    int dy_total = y2 - y0;
    if (dy_total == 0) return;

    for (int y = y0; y < y2; y++) {
        if (y < t->cy1 || y > t->cy2) continue;

        int second_half = (y >= y1);
        int seg_height = second_half ? (y2 - y1) : (y1 - y0);
        if (seg_height == 0) seg_height = 1;

        float alpha = (float)(y - y0) / (float)dy_total;
        float beta;
        if (second_half)
            beta = (float)(y - y1) / (float)seg_height;
        else
            beta = (float)(y - y0) / (float)seg_height;

        int xa = x0 + (int)((float)(x2 - x0) * alpha);
        int xb;
        if (second_half)
            xb = x1 + (int)((float)(x2 - x1) * beta);
        else
            xb = x0 + (int)((float)(x1 - x0) * beta);

        if (xa > xb) { int tt = xa; xa = xb; xb = tt; }

        int sx = max_i(xa, t->cx1);
        int ex = min_i(xb, t->cx2 + 1);
        fast_span_opaque(t, st, y, sx, ex, color);
    }
}

static void fastr_gouraud_triangle(const RTarget *t, const RState *st,
                                   int x0, int y0, uint16_t c0,
                                   int x1, int y1, uint16_t c1,
                                   int x2, int y2, uint16_t c2) {
    int r0 = (c0 >>  0) & 0x1F, g0 = (c0 >>  5) & 0x1F, b0 = (c0 >> 10) & 0x1F;
    int r1 = (c1 >>  0) & 0x1F, g1 = (c1 >>  5) & 0x1F, b1 = (c1 >> 10) & 0x1F;
    int r2 = (c2 >>  0) & 0x1F, g2 = (c2 >>  5) & 0x1F, b2 = (c2 >> 10) & 0x1F;

    if (y0 > y1) {
        int tt; tt=x0; x0=x1; x1=tt; tt=y0; y0=y1; y1=tt;
        tt=r0; r0=r1; r1=tt; tt=g0; g0=g1; g1=tt; tt=b0; b0=b1; b1=tt;
    }
    if (y0 > y2) {
        int tt; tt=x0; x0=x2; x2=tt; tt=y0; y0=y2; y2=tt;
        tt=r0; r0=r2; r2=tt; tt=g0; g0=g2; g2=tt; tt=b0; b0=b2; b2=tt;
    }
    if (y1 > y2) {
        int tt; tt=x1; x1=x2; x2=tt; tt=y1; y1=y2; y2=tt;
        tt=r1; r1=r2; r2=tt; tt=g1; g1=g2; g2=tt; tt=b1; b1=b2; b2=tt;
    }

    int dy_total = y2 - y0;
    if (dy_total == 0) return;

    for (int y = y0; y < y2; y++) {
        if (y < t->cy1 || y > t->cy2) continue;

        int second_half = (y >= y1);
        int seg_height = second_half ? (y2 - y1) : (y1 - y0);
        if (seg_height == 0) seg_height = 1;

        float alpha = (float)(y - y0) / (float)dy_total;
        float beta;
        if (second_half)
            beta = (float)(y - y1) / (float)seg_height;
        else
            beta = (float)(y - y0) / (float)seg_height;

        int xa = x0 + (int)((float)(x2 - x0) * alpha);
        int xb;
        if (second_half)
            xb = x1 + (int)((float)(x2 - x1) * beta);
        else
            xb = x0 + (int)((float)(x1 - x0) * beta);

        int ra = r0 + (int)((float)(r2 - r0) * alpha);
        int ga = g0 + (int)((float)(g2 - g0) * alpha);
        int ba = b0 + (int)((float)(b2 - b0) * alpha);
        int rb, gb, bb;
        if (second_half) {
            rb = r1 + (int)((float)(r2 - r1) * beta);
            gb = g1 + (int)((float)(g2 - g1) * beta);
            bb = b1 + (int)((float)(b2 - b1) * beta);
        } else {
            rb = r0 + (int)((float)(r1 - r0) * beta);
            gb = g0 + (int)((float)(g1 - g0) * beta);
            bb = b0 + (int)((float)(b1 - b0) * beta);
        }

        if (xa > xb) {
            int tt;
            tt = xa; xa = xb; xb = tt;
            tt = ra; ra = rb; rb = tt;
            tt = ga; ga = gb; gb = tt;
            tt = ba; ba = bb; bb = tt;
        }

        int sx = max_i(xa, t->cx1);
        int ex = min_i(xb, t->cx2 + 1);
        int span = xb - xa;

        if (y < 0 || y >= t->h) continue;
        if (sx < 0) sx = 0;
        if (ex > t->w) ex = t->w;
        uint16_t *rowp = t->buf + (size_t)y * t->w;
        if (span > 0) {
            const double inv_span = 1.0 / (double)span;   /* exact-div (see header) */
            double dk = (double)(sx - xa);
            const float fdr = (float)(rb - ra), fdg = (float)(gb - ga), fdb = (float)(bb - ba);
            for (int x = sx; x < ex; x++, dk += 1.0) {
                float tf = (float)(dk * inv_span);
                int r = ra + (int)(fdr * tf);
                int g = ga + (int)(fdg * tf);
                int b = ba + (int)(fdb * tf);
                if (r < 0) r = 0; if (r > 31) r = 31;
                if (g < 0) g = 0; if (g > 31) g = 31;
                if (b < 0) b = 0; if (b > 31) b = 31;
                fast_put_opaque(st, rowp + x, (uint16_t)(r | (g << 5) | (b << 10)));
            }
        } else {
            const uint16_t color = (uint16_t)(ra | (ga << 5) | (ba << 10));
            for (int x = sx; x < ex; x++) fast_put_opaque(st, rowp + x, color);
        }
    }
}

static void fastr_textured_triangle(const RTarget *t, const RState *st,
                                    int x0, int y0, int u0, int v0,
                                    int x1, int y1, int u1, int v1,
                                    int x2, int y2, int u2, int v2,
                                    uint16_t clut_x, uint16_t clut_y,
                                    uint16_t texpage) {
    if (y0 > y1) {
        int tt;
        tt=x0; x0=x1; x1=tt; tt=y0; y0=y1; y1=tt;
        tt=u0; u0=u1; u1=tt; tt=v0; v0=v1; v1=tt;
    }
    if (y0 > y2) {
        int tt;
        tt=x0; x0=x2; x2=tt; tt=y0; y0=y2; y2=tt;
        tt=u0; u0=u2; u2=tt; tt=v0; v0=v2; v2=tt;
    }
    if (y1 > y2) {
        int tt;
        tt=x1; x1=x2; x2=tt; tt=y1; y1=y2; y2=tt;
        tt=u1; u1=u2; u2=tt; tt=v1; v1=v2; v2=tt;
    }

    int dy_total = y2 - y0;
    if (dy_total == 0) return;

    FastTex ft; fast_tex_init(&ft, st, texpage, clut_x, clut_y);
    const int mr = st->mod_r, mg = st->mod_g, mb = st->mod_b, raw = st->raw;

    for (int y = y0; y < y2; y++) {
        if (y < t->cy1 || y > t->cy2) continue;

        int second_half = (y >= y1);
        int seg_height = second_half ? (y2 - y1) : (y1 - y0);
        if (seg_height == 0) seg_height = 1;

        float alpha = (float)(y - y0) / (float)dy_total;
        float beta;
        if (second_half)
            beta = (float)(y - y1) / (float)seg_height;
        else
            beta = (float)(y - y0) / (float)seg_height;

        int xa = x0 + (int)((float)(x2 - x0) * alpha);
        int xb;
        if (second_half)
            xb = x1 + (int)((float)(x2 - x1) * beta);
        else
            xb = x0 + (int)((float)(x1 - x0) * beta);

        float ua = u0 + (float)(u2 - u0) * alpha;
        float va = v0 + (float)(v2 - v0) * alpha;
        float ub, vb;
        if (second_half) {
            ub = u1 + (float)(u2 - u1) * beta;
            vb = v1 + (float)(v2 - v1) * beta;
        } else {
            ub = u0 + (float)(u1 - u0) * beta;
            vb = v0 + (float)(v1 - v0) * beta;
        }

        if (xa > xb) {
            int tt = xa; xa = xb; xb = tt;
            float tf;
            tf = ua; ua = ub; ub = tf;
            tf = va; va = vb; vb = tf;
        }

        int span = xb - xa;
        if (span == 0) span = 1;

        int sx = max_i(xa, t->cx1);
        int ex = min_i(xb, t->cx2 + 1);

        if (y < 0 || y >= t->h) continue;
        if (sx < 0) sx = 0;
        if (ex > t->w) ex = t->w;
        uint16_t *rowp = t->buf + (size_t)y * t->w;
        const double inv_span = 1.0 / (double)span;   /* exact-div (see header) */
        double dk = (double)(sx - xa);
        const float dU = ub - ua, dV = vb - va;
        for (int x = sx; x < ex; x++, dk += 1.0) {
            float t_val = (float)(dk * inv_span);
            float fu = ua + dU * t_val;
            float fv = va + dV * t_val;
            fast_put_textured(st, rowp + x, fast_tex_fetch(&ft, (int)fu & 0xFF, (int)fv & 0xFF),
                              mr, mg, mb, raw);
        }
    }
}

static void fastr_shaded_textured_triangle(const RTarget *t, const RState *st,
                                           int x0, int y0, int u0, int v0,
                                           int r0, int g0, int b0,
                                           int x1, int y1, int u1, int v1,
                                           int r1, int g1, int b1,
                                           int x2, int y2, int u2, int v2,
                                           int r2, int g2, int b2,
                                           uint16_t clut_x, uint16_t clut_y,
                                           uint16_t texpage, int raw_texture) {
    if (y0 > y1) {
        int tt;
        tt=x0; x0=x1; x1=tt; tt=y0; y0=y1; y1=tt;
        tt=u0; u0=u1; u1=tt; tt=v0; v0=v1; v1=tt;
        tt=r0; r0=r1; r1=tt; tt=g0; g0=g1; g1=tt; tt=b0; b0=b1; b1=tt;
    }
    if (y0 > y2) {
        int tt;
        tt=x0; x0=x2; x2=tt; tt=y0; y0=y2; y2=tt;
        tt=u0; u0=u2; u2=tt; tt=v0; v0=v2; v2=tt;
        tt=r0; r0=r2; r2=tt; tt=g0; g0=g2; g2=tt; tt=b0; b0=b2; b2=tt;
    }
    if (y1 > y2) {
        int tt;
        tt=x1; x1=x2; x2=tt; tt=y1; y1=y2; y2=tt;
        tt=u1; u1=u2; u2=tt; tt=v1; v1=v2; v2=tt;
        tt=r1; r1=r2; r2=tt; tt=g1; g1=g2; g2=tt; tt=b1; b1=b2; b2=tt;
    }

    int dy_total = y2 - y0;
    if (dy_total == 0) return;

    FastTex ft; fast_tex_init(&ft, st, texpage, clut_x, clut_y);

    for (int y = y0; y < y2; y++) {
        if (y < t->cy1 || y > t->cy2) continue;

        int second_half = (y >= y1);
        int seg_height = second_half ? (y2 - y1) : (y1 - y0);
        if (seg_height == 0) seg_height = 1;

        float alpha = (float)(y - y0) / (float)dy_total;
        float beta;
        if (second_half)
            beta = (float)(y - y1) / (float)seg_height;
        else
            beta = (float)(y - y0) / (float)seg_height;

        int xa = x0 + (int)((float)(x2 - x0) * alpha);
        int xb;
        if (second_half)
            xb = x1 + (int)((float)(x2 - x1) * beta);
        else
            xb = x0 + (int)((float)(x1 - x0) * beta);

        float ua = u0 + (float)(u2 - u0) * alpha;
        float va = v0 + (float)(v2 - v0) * alpha;
        float ra = r0 + (float)(r2 - r0) * alpha;
        float ga = g0 + (float)(g2 - g0) * alpha;
        float ba = b0 + (float)(b2 - b0) * alpha;

        float ub, vb, rb, gb, bb;
        if (second_half) {
            ub = u1 + (float)(u2 - u1) * beta;
            vb = v1 + (float)(v2 - v1) * beta;
            rb = r1 + (float)(r2 - r1) * beta;
            gb = g1 + (float)(g2 - g1) * beta;
            bb = b1 + (float)(b2 - b1) * beta;
        } else {
            ub = u0 + (float)(u1 - u0) * beta;
            vb = v0 + (float)(v1 - v0) * beta;
            rb = r0 + (float)(r1 - r0) * beta;
            gb = g0 + (float)(g1 - g0) * beta;
            bb = b0 + (float)(b1 - b0) * beta;
        }

        if (xa > xb) {
            int tt = xa; xa = xb; xb = tt;
            float tf;
            tf = ua; ua = ub; ub = tf;
            tf = va; va = vb; vb = tf;
            tf = ra; ra = rb; rb = tf;
            tf = ga; ga = gb; gb = tf;
            tf = ba; ba = bb; bb = tf;
        }

        int span = xb - xa;
        if (span == 0) span = 1;

        int sx = max_i(xa, t->cx1);
        int ex = min_i(xb, t->cx2 + 1);

        if (y < 0 || y >= t->h) continue;
        if (sx < 0) sx = 0;
        if (ex > t->w) ex = t->w;
        uint16_t *rowp = t->buf + (size_t)y * t->w;
        const double inv_span = 1.0 / (double)span;   /* exact-div (see header) */
        double dk = (double)(sx - xa);
        const float dU = ub - ua, dV = vb - va, dR = rb - ra, dG = gb - ga, dB = bb - ba;
        for (int x = sx; x < ex; x++, dk += 1.0) {
            float t_val = (float)(dk * inv_span);
            float fu = ua + dU * t_val;
            float fv = va + dV * t_val;
            int mr = (int)(ra + dR * t_val);
            int mg = (int)(ga + dG * t_val);
            int mb = (int)(ba + dB * t_val);
            if (mr < 0) mr = 0; if (mr > 31) mr = 31;
            if (mg < 0) mg = 0; if (mg > 31) mg = 31;
            if (mb < 0) mb = 0; if (mb > 31) mb = 31;
            fast_put_textured(st, rowp + x, fast_tex_fetch(&ft, (int)fu & 0xFF, (int)fv & 0xFF),
                              mr, mg, mb, raw_texture);
        }
    }
}

static void fastr_flat_rect(const RTarget *t, const RState *st, int x, int y, int w, int h,
                            uint16_t color) {
    for (int row = 0; row < h; row++) {
        int py = y + row;
        if (py < t->cy1 || py > t->cy2) continue;

        int sx = max_i(x, t->cx1);
        int ex = min_i(x + w - 1, t->cx2);
        fast_span_opaque(t, st, py, sx, ex + 1, color);
    }
}

static void fastr_textured_rect(const RTarget *t, const RState *st, int x, int y, int w, int h,
                                int u, int v, uint16_t clut_x, uint16_t clut_y, uint16_t texpage) {
    const int s = t->s;
    FastTex ft; fast_tex_init(&ft, st, texpage, clut_x, clut_y);
    const int mr = st->mod_r, mg = st->mod_g, mb = st->mod_b, raw = st->raw;
    const int cx1 = max_i(t->cx1, 0), cx2 = min_i(t->cx2, t->w - 1);
    const int cy1 = max_i(t->cy1, 0), cy2 = min_i(t->cy2, t->h - 1);
    const int col0 = max_i(0, cx1 - x), col1 = min_i(w - 1, cx2 - x);
    const int row0 = max_i(0, cy1 - y), row1 = min_i(h - 1, cy2 - y);
    if (col0 > col1) return;
    for (int row = row0; row <= row1; row++) {
        const int py = y + row;
        const int tv = (v + row / s) & 0xFF;
        uint16_t *rowp = t->buf + (size_t)py * t->w;
        if (s == 1) {
            for (int col = col0; col <= col1; col++)
                fast_put_textured(st, rowp + (x + col), fast_tex_fetch(&ft, (u + col) & 0xFF, tv),
                                  mr, mg, mb, raw);
        } else {
            for (int col = col0; col <= col1; col++)
                fast_put_textured(st, rowp + (x + col), fast_tex_fetch(&ft, (u + col / s) & 0xFF, tv),
                                  mr, mg, mb, raw);
        }
    }
}

static void fastr_textured_rect_scaled(const RTarget *t, const RState *st, int x, int y, int w, int h,
                                       int u0, int v0, int u1, int v1,
                                       uint16_t clut_x, uint16_t clut_y, uint16_t texpage) {
    if (w <= 0 || h <= 0) return;
    const int du = u1 - u0, dv = v1 - v0;
    FastTex ft; fast_tex_init(&ft, st, texpage, clut_x, clut_y);
    const int mr = st->mod_r, mg = st->mod_g, mb = st->mod_b, raw = st->raw;
    const int cx1 = max_i(t->cx1, 0), cx2 = min_i(t->cx2, t->w - 1);
    const int cy1 = max_i(t->cy1, 0), cy2 = min_i(t->cy2, t->h - 1);
    const int col0 = max_i(0, cx1 - x), col1 = min_i(w - 1, cx2 - x);
    const int row0 = max_i(0, cy1 - y), row1 = min_i(h - 1, cy2 - y);
    if (col0 > col1) return;
    /* trunc((du * col) / w) == sign(du) * floor(|du| * col / w) for w > 0, col >= 0 */
    const int neg = du < 0;
    const int64_t adu = neg ? -(int64_t)du : (int64_t)du;
    const int64_t sq = adu / w, sr = adu % w;
    const int64_t n0 = adu * col0, q0 = n0 / w, r0 = n0 % w;
    for (int row = row0; row <= row1; row++) {
        const int py = y + row;
        const int tv = (int)(v0 + ((int64_t)dv * row) / h) & 0xFF;
        uint16_t *rowp = t->buf + (size_t)py * t->w;
        int64_t q = q0, r = r0;
        for (int col = col0; col <= col1; col++) {
            const int tu = (int)(u0 + (neg ? -q : q)) & 0xFF;
            fast_put_textured(st, rowp + (x + col), fast_tex_fetch(&ft, tu, tv), mr, mg, mb, raw);
            q += sq; r += sr;
            if (r >= w) { r -= w; q++; }
        }
    }
}

/* Wide pass of sw_draw_line / sw_draw_shaded_line at scale 1: the same Bresenham walk, each
 * point written like wide_put_block_opaque (x translated by tdx). */
static void fastr_line_wide(const RTarget *t, const RState *st, int tdx,
                            int x0, int y0, int x1, int y1, uint16_t color) {
    int dx = abs(x1 - x0);
    int dy = -abs(y1 - y0);
    int sx = (x0 < x1) ? 1 : -1;
    int sy = (y0 < y1) ? 1 : -1;
    int err = dx + dy;
    for (;;) {
        fast_put_opaque_checked(t, st, x0 + tdx, y0, color);
        if (x0 == x1 && y0 == y1) break;
        int e2 = 2 * err;
        if (e2 >= dy) { err += dy; x0 += sx; }
        if (e2 <= dx) { err += dx; y0 += sy; }
    }
}

static void fastr_shaded_line_wide(const RTarget *t, const RState *st, int tdx,
                                   int x0, int y0, uint16_t c0, int x1, int y1, uint16_t c1) {
    int dx = abs(x1 - x0);
    int dy = -abs(y1 - y0);
    int sx = (x0 < x1) ? 1 : -1;
    int sy = (y0 < y1) ? 1 : -1;
    int err = dx + dy;
    int total = max_i(abs(x1 - x0), abs(y1 - y0));
    if (total == 0) total = 1;
    int r0 = c0 & 0x1F, g0 = (c0 >> 5) & 0x1F, b0 = (c0 >> 10) & 0x1F;
    int r1 = c1 & 0x1F, g1 = (c1 >> 5) & 0x1F, b1 = (c1 >> 10) & 0x1F;
    int step = 0;
    for (;;) {
        int r = r0 + (r1 - r0) * step / total;
        int g = g0 + (g1 - g0) * step / total;
        int b = b0 + (b1 - b0) * step / total;
        fast_put_opaque_checked(t, st, x0 + tdx, y0, (uint16_t)(r | (g << 5) | (b << 10)));
        if (x0 == x1 && y0 == y1) break;
        int e2 = 2 * err;
        if (e2 >= dy) { err += dy; x0 += sx; }
        if (e2 <= dx) { err += dx; y0 += sy; }
        step++;
    }
}

/* ---- Native-wide worker ------------------------------------------------------------- */
enum { WK_FLAT_TRI = 1, WK_GOU_TRI, WK_TEX_TRI, WK_STEX_TRI, WK_FLAT_RECT, WK_TEX_RECT,
       WK_TEX_RECT_SCALED, WK_LINE, WK_SLINE, WK_FILL_ROWS, WK_FILL_MARGINS };

typedef struct {
    int     kind;
    RState  st;
    RTarget t;
    int     p[28];
} WkCmd;

static unsigned long long wk_cmds = 0;    /* commands queued (diagnostic, [FPS] line) */
static unsigned long long wk_waits = 0;   /* times the emu thread had to wait (diagnostic) */

static void wk_exec(const WkCmd *c) {
    const int *p = c->p;
    switch (c->kind) {
    case WK_FLAT_TRI:
        fastr_flat_triangle(&c->t, &c->st, p[0], p[1], p[2], p[3], p[4], p[5], (uint16_t)p[6]);
        break;
    case WK_GOU_TRI:
        fastr_gouraud_triangle(&c->t, &c->st, p[0], p[1], (uint16_t)p[2], p[3], p[4], (uint16_t)p[5],
                               p[6], p[7], (uint16_t)p[8]);
        break;
    case WK_TEX_TRI:
        fastr_textured_triangle(&c->t, &c->st, p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7],
                                p[8], p[9], p[10], p[11], (uint16_t)p[12], (uint16_t)p[13], (uint16_t)p[14]);
        break;
    case WK_STEX_TRI:
        fastr_shaded_textured_triangle(&c->t, &c->st,
            p[0], p[1], p[2], p[3], p[4], p[5], p[6],
            p[7], p[8], p[9], p[10], p[11], p[12], p[13],
            p[14], p[15], p[16], p[17], p[18], p[19], p[20],
            (uint16_t)p[21], (uint16_t)p[22], (uint16_t)p[23], p[24]);
        break;
    case WK_FLAT_RECT:
        fastr_flat_rect(&c->t, &c->st, p[0], p[1], p[2], p[3], (uint16_t)p[4]);
        break;
    case WK_TEX_RECT:
        fastr_textured_rect(&c->t, &c->st, p[0], p[1], p[2], p[3], p[4], p[5],
                            (uint16_t)p[6], (uint16_t)p[7], (uint16_t)p[8]);
        break;
    case WK_TEX_RECT_SCALED:
        fastr_textured_rect_scaled(&c->t, &c->st, p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7],
                                   (uint16_t)p[8], (uint16_t)p[9], (uint16_t)p[10]);
        break;
    case WK_LINE:
        fastr_line_wide(&c->t, &c->st, p[0], p[1], p[2], p[3], p[4], (uint16_t)p[5]);
        break;
    case WK_SLINE:
        fastr_shaded_line_wide(&c->t, &c->st, p[0], p[1], p[2], (uint16_t)p[3], p[4], p[5], (uint16_t)p[6]);
        break;
    case WK_FILL_ROWS:       /* sw_wide_clear body */
        for (int row = p[0]; row < p[1]; row++) {
            uint16_t *dst = c->t.buf + (size_t)row * c->t.w;
            for (int col = 0; col < c->t.w; col++) dst[col] = (uint16_t)p[2];
        }
        break;
    case WK_FILL_MARGINS:    /* sw_wide_clear_margins body */
        for (int row = p[0]; row < p[1]; row++) {
            uint16_t *dst = c->t.buf + (size_t)row * c->t.w;
            if (p[4] & 1) for (int col = 0; col < p[3]; col++) dst[col] = (uint16_t)p[2];
            if (p[4] & 2) for (int col = c->t.w - p[3]; col < c->t.w; col++) dst[col] = (uint16_t)p[2];
        }
        break;
    default:
        break;
    }
}

#if defined(_WIN32)
#ifndef NOMINMAX
#define NOMINMAX
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>

#define WK_CAP 4096                         /* commands in flight (power of two) */
static WkCmd *wk_ring = NULL;
static volatile LONG64 wk_head = 0;         /* commands queued; only the emu thread writes it */
static volatile LONG64 wk_tail = 0;         /* commands done; only the worker writes it */
static volatile LONG wk_sleeping = 0;
static SRWLOCK wk_lock = SRWLOCK_INIT;
static CONDITION_VARIABLE wk_cv = CONDITION_VARIABLE_INIT;
static int wk_state = -1;                   /* -1 not started, 0 unavailable, 1 running */

static inline LONG64 wk_load(volatile LONG64 *p) { return InterlockedOr64(p, 0); }   /* full barrier */

static DWORD WINAPI wk_main(LPVOID arg) {
    (void)arg;
    for (;;) {
        const LONG64 t = wk_tail;
        if (wk_load(&wk_head) == t) {
            for (int i = 0; i < 4000 && wk_load(&wk_head) == t; i++) YieldProcessor();
            if (wk_load(&wk_head) == t) {
                AcquireSRWLockExclusive(&wk_lock);
                InterlockedExchange(&wk_sleeping, 1);
                while (wk_load(&wk_head) == t)
                    SleepConditionVariableSRW(&wk_cv, &wk_lock, INFINITE, 0);
                InterlockedExchange(&wk_sleeping, 0);
                ReleaseSRWLockExclusive(&wk_lock);
            }
            continue;
        }
        wk_exec(&wk_ring[t & (WK_CAP - 1)]);
        InterlockedExchange64(&wk_tail, t + 1);
    }
}

static int wk_start(void) {
    if (wk_state >= 0) return wk_state;
    wk_state = 0;
    wk_ring = (WkCmd *)malloc(sizeof(WkCmd) * WK_CAP);
    if (!wk_ring) return 0;
    HANDLE h = CreateThread(NULL, 0, wk_main, NULL, 0, NULL);
    if (!h) { free(wk_ring); wk_ring = NULL; return 0; }
    CloseHandle(h);
    wk_state = 1;
    return 1;
}

/* Emu thread: wait until the worker has finished the first `done` commands. */
static void wk_wait_until(LONG64 done) {
    if (wk_load(&wk_tail) >= done) return;
    wk_waits++;
    for (int i = 0; wk_load(&wk_tail) < done; i++) {
        if (i < 20000) YieldProcessor(); else Sleep(0);
    }
}

/* VRAM rects (inclusive) that queued commands read (texels, CLUTs), each with the index of its
 * last reader: a canonical write that overlaps one waits only until that reader is done. */
#define WK_MAXR 16
typedef struct { int x1, y1, x2, y2; LONG64 last; } WkRect;
static WkRect wk_rr[WK_MAXR];
static int wk_nr = 0;

static void wk_drain(void) {
    if (wk_state <= 0) return;
    wk_wait_until(wk_head);
    wk_nr = 0;
}

/* A free slot for the wide pass, or NULL when it must stay inline (worker unavailable,
 * supersampling, bilinear): pending wide work is then drained so wide writes stay ordered. */
static WkCmd *wk_begin(void) {
    if (g_scale != 1 || g_texture_filter || wk_start() <= 0) { wk_drain(); return NULL; }
    const LONG64 h = wk_head;
    wk_wait_until(h - WK_CAP + 1);           /* slot h is free once command h - WK_CAP is done */
    return &wk_ring[h & (WK_CAP - 1)];
}

static void wk_commit(void) {
    wk_cmds++;
    InterlockedExchange64(&wk_head, wk_head + 1);
    if (InterlockedOr(&wk_sleeping, 0)) {
        AcquireSRWLockExclusive(&wk_lock);
        WakeConditionVariable(&wk_cv);
        ReleaseSRWLockExclusive(&wk_lock);
    }
}

/* The command being filled (index wk_head) reads [x1..x2]x[y1..y2]. */
static void wk_note_read(int x1, int y1, int x2, int y2) {
    const LONG64 idx = wk_head;
    for (int i = 0; i < wk_nr; i++) {
        WkRect *r = &wk_rr[i];
        if (x1 >= r->x1 && y1 >= r->y1 && x2 <= r->x2 && y2 <= r->y2) { r->last = idx; return; }
    }
    if (wk_nr == WK_MAXR) {                  /* forget rects whose readers are all done */
        const LONG64 done = wk_load(&wk_tail);
        int n = 0;
        for (int i = 0; i < wk_nr; i++) if (wk_rr[i].last >= done) wk_rr[n++] = wk_rr[i];
        wk_nr = n;
    }
    if (wk_nr < WK_MAXR) {
        WkRect *r = &wk_rr[wk_nr++];
        r->x1 = x1; r->y1 = y1; r->x2 = x2; r->y2 = y2; r->last = idx;
        return;
    }
    int best = 0;
    long long best_g = -1;
    for (int i = 0; i < WK_MAXR; i++) {      /* full: merge into the rect that grows least */
        const WkRect *r = &wk_rr[i];
        const long long a0 = (long long)(r->x2 - r->x1 + 1) * (long long)(r->y2 - r->y1 + 1);
        const long long a1 = (long long)(max_i(r->x2, x2) - min_i(r->x1, x1) + 1) *
                             (long long)(max_i(r->y2, y2) - min_i(r->y1, y1) + 1);
        if (best_g < 0 || a1 - a0 < best_g) { best_g = a1 - a0; best = i; }
    }
    WkRect *r = &wk_rr[best];
    r->x1 = min_i(r->x1, x1); r->y1 = min_i(r->y1, y1);
    r->x2 = max_i(r->x2, x2); r->y2 = max_i(r->y2, y2);
    r->last = idx;
}

/* VRAM a textured primitive can read: texels for its uv extent and its CLUT entries. u/v come
 * from the GP0 words (0..255); the float interpolation can land one texel inside the extent's
 * low edge (truncation), hence the -1 margin. A texture window or an extent that wraps => the
 * whole 0..255 range. */
static void wk_note_tex(const RState *s, uint16_t texpage, uint16_t clut_x, uint16_t clut_y,
                        int umin, int umax, int vmin, int vmax) {
    if (s->tw_mask_x || umin < 0 || umax > 255) { umin = 0; umax = 255; }
    else { umin = max_i(umin - 1, 0); umax = min_i(umax + 1, 255); }
    if (s->tw_mask_y || vmin < 0 || vmax > 255) { vmin = 0; vmax = 255; }
    else { vmin = max_i(vmin - 1, 0); vmax = min_i(vmax + 1, 255); }
    const int depth = (texpage >> 7) & 3;
    const int tpx = (texpage & 0xF) * 64, tpy = ((texpage >> 4) & 1) * 256;
    int x1, x2;
    if (depth == 0)      { x1 = tpx + (umin >> 2); x2 = tpx + (umax >> 2); }
    else if (depth == 1) { x1 = tpx + (umin >> 1); x2 = tpx + (umax >> 1); }
    else                 { x1 = tpx + umin;        x2 = tpx + umax; }
    if (x1 > VRAM_WIDTH - 1) {               /* the fetch wraps the column (& 1023) */
        wk_note_read(x1 - VRAM_WIDTH, tpy + vmin, x2 - VRAM_WIDTH, tpy + vmax);
    } else if (x2 > VRAM_WIDTH - 1) {
        wk_note_read(x1, tpy + vmin, VRAM_WIDTH - 1, tpy + vmax);
        wk_note_read(0, tpy + vmin, x2 - VRAM_WIDTH, tpy + vmax);
    } else {
        wk_note_read(x1, tpy + vmin, x2, tpy + vmax);
    }
    if (depth < 2) {
        const int cy = clut_y & (VRAM_HEIGHT - 1);
        const int cx1 = clut_x & (VRAM_WIDTH - 1);
        const int cx2 = cx1 + (depth == 0 ? 15 : 255);
        if (cx2 > VRAM_WIDTH - 1) {
            wk_note_read(cx1, cy, VRAM_WIDTH - 1, cy);
            wk_note_read(0, cy, cx2 - VRAM_WIDTH, cy);
        } else {
            wk_note_read(cx1, cy, cx2, cy);
        }
    }
}

/* Before a canonical VRAM write to [x1..x2]x[y1..y2]: wait for the queued readers there. */
static void wk_hazard(int x1, int y1, int x2, int y2) {
    for (int i = 0; i < wk_nr; ) {
        const WkRect *r = &wk_rr[i];
        if (x2 < r->x1 || x1 > r->x2 || y2 < r->y1 || y1 > r->y2) { i++; continue; }
        wk_wait_until(r->last + 1);
        wk_rr[i] = wk_rr[--wk_nr];
    }
}
#else
static void wk_drain(void) { }
static WkCmd *wk_begin(void) { return NULL; }
static void wk_commit(void) { }
static void wk_note_tex(const RState *s, uint16_t texpage, uint16_t clut_x, uint16_t clut_y,
                        int umin, int umax, int vmin, int vmax) {
    (void)s; (void)texpage; (void)clut_x; (void)clut_y; (void)umin; (void)umax; (void)vmin; (void)vmax;
}
static void wk_hazard(int x1, int y1, int x2, int y2) { (void)x1; (void)y1; (void)x2; (void)y2; }
#endif

#define wk_hazard_clip() wk_hazard(g_clip_x1, g_clip_y1, g_clip_x2, g_clip_y2)

/* A canonical write to a VRAM rect that wraps at the edges (fills, copies, uploads). */
static void wk_hazard_wrapped(int x, int y, int w, int h) {
    if (w <= 0 || h <= 0) return;
    if (w > VRAM_WIDTH) w = VRAM_WIDTH;
    if (h > VRAM_HEIGHT) h = VRAM_HEIGHT;
    const int x0 = x & (VRAM_WIDTH - 1), y0 = y & (VRAM_HEIGHT - 1);
    const int xe = x0 + w - 1, ye = y0 + h - 1;
    const int xa = min_i(xe, VRAM_WIDTH - 1), ya = min_i(ye, VRAM_HEIGHT - 1);
    wk_hazard(x0, y0, xa, ya);
    if (xe > VRAM_WIDTH - 1) wk_hazard(0, y0, xe - VRAM_WIDTH, ya);
    if (ye > VRAM_HEIGHT - 1) wk_hazard(x0, 0, xa, ye - VRAM_HEIGHT);
    if (xe > VRAM_WIDTH - 1 && ye > VRAM_HEIGHT - 1) wk_hazard(0, 0, xe - VRAM_WIDTH, ye - VRAM_HEIGHT);
}

static inline int min3_i(int a, int b, int c) { return min_i(a, min_i(b, c)); }
static inline int max3_i(int a, int b, int c) { return max_i(a, max_i(b, c)); }

/* ---- end of fast paths / worker ---- */

/* Per-prim uv sampling bounds (inclusive), Beetle-PSX model: bilinear'''


def funcion(t, firma):
    """(inicio, fin) del texto de la función que empieza por «firma» (hasta su «}» de la columna 0)."""
    if t.count(firma) != 1:
        raise SystemExit(f'{firma!r}: {t.count(firma)} veces')
    a = t.index(firma)
    b = t.index('\n}\n', a) + 3
    return a, b


def reemplazar_funcion(t, firma, nuevo):
    a, b = funcion(t, firma)
    return t[:a] + nuevo + t[b:]


def insertar_al_principio(t, firma, texto):
    """Inserta «texto» justo después de la llave de apertura de la función «firma»."""
    a, _ = funcion(t, firma)
    c = t.index('{\n', a) + 2
    return t[:c] + texto + t[c:]


def sustituir(t, viejo, nuevo):
    if t.count(viejo) != 1:
        raise SystemExit(f'{t.count(viejo)} veces: {viejo[:80]!r}')
    return t.replace(viejo, nuevo)


def parchear_renderer(t):
    t = sustituir(t, '/* Per-prim uv sampling bounds (inclusive), Beetle-PSX model: bilinear', BLOQUE)

    # rasterizadores: los caminos rápidos con el estado de las globales (hilo del emulador)
    t = reemplazar_funcion(t, 'static void raster_flat_triangle(const RTarget *t,', '''static void raster_flat_triangle(const RTarget *t,
                                 int x0, int y0, int x1, int y1,
                                 int x2, int y2, uint16_t color) {
    RState st; rstate_globals(&st);
    fastr_flat_triangle(t, &st, x0, y0, x1, y1, x2, y2, color);   /* fast path (bit-identical) */
}
''')
    t = reemplazar_funcion(t, 'static void raster_gouraud_triangle(const RTarget *t,', '''static void raster_gouraud_triangle(const RTarget *t,
                                    int x0, int y0, uint16_t c0,
                                    int x1, int y1, uint16_t c1,
                                    int x2, int y2, uint16_t c2) {
    RState st; rstate_globals(&st);
    fastr_gouraud_triangle(t, &st, x0, y0, c0, x1, y1, c1, x2, y2, c2);   /* fast path (bit-identical) */
}
''')
    t = insertar_al_principio(t, 'static void raster_textured_triangle(const RTarget *t,', '''    if (!g_texture_filter) {   /* fast path (bit-identical) */
        RState st; rstate_globals(&st);
        fastr_textured_triangle(t, &st, x0, y0, u0, v0, x1, y1, u1, v1, x2, y2, u2, v2,
                                clut_x, clut_y, texpage);
        return;
    }
''')
    t = insertar_al_principio(t, 'static void raster_shaded_textured_triangle(const RTarget *t,', '''    if (!g_texture_filter) {   /* fast path (bit-identical) */
        RState st; rstate_globals(&st);
        fastr_shaded_textured_triangle(t, &st, x0, y0, u0, v0, r0, g0, b0, x1, y1, u1, v1, r1, g1, b1,
                                       x2, y2, u2, v2, r2, g2, b2, clut_x, clut_y, texpage, raw_texture);
        return;
    }
''')
    t = reemplazar_funcion(t, 'static void raster_flat_rect(const RTarget *t, int x, int y, int w, int h,', '''static void raster_flat_rect(const RTarget *t, int x, int y, int w, int h,
                             uint16_t color) {
    RState st; rstate_globals(&st);
    fastr_flat_rect(t, &st, x, y, w, h, color);   /* fast path (bit-identical) */
}
''')
    t = insertar_al_principio(t, 'static void raster_textured_rect(const RTarget *t, int x, int y, int w, int h,', '''    if (!g_texture_filter) {   /* fast path (bit-identical) */
        RState st; rstate_globals(&st);
        fastr_textured_rect(t, &st, x, y, w, h, u, v, clut_x, clut_y, texpage);
        return;
    }
''')
    # la definición, no la declaración adelantada (que acaba en «;»)
    a = t.index('static void raster_textured_rect_scaled(const RTarget *t, int x, int y,\n                                        int w, int h,')
    c = t.index('{\n', a) + 2
    t = t[:c] + '''    if (!g_texture_filter) {   /* fast path (bit-identical) */
        RState st; rstate_globals(&st);
        fastr_textured_rect_scaled(t, &st, x, y, w, h, u0, v0, u1, v1, clut_x, clut_y, texpage);
        return;
    }
''' + t[c:]

    # pasadas anchas al hilo
    t = reemplazar_funcion(t, 'void sw_draw_flat_triangle(int x0, int y0, int x1, int y1,', '''void sw_draw_flat_triangle(int x0, int y0, int x1, int y1,
                           int x2, int y2, uint16_t color) {
    wk_hazard_clip();
    RTarget n = rt_native();
    raster_flat_triangle(&n, x0, y0, x1, y1, x2, y2, color);
    if (g_hr) {
        int s = g_scale;
        RTarget hr = rt_hires();
        raster_flat_triangle(&hr, x0*s, y0*s, x1*s, y1*s, x2*s, y2*s, color);
    }
    if (g_wide_cur) {
        int s = g_scale, dx = wide_dx();
        RTarget wt = rt_wide();
        WideBd bd = wide_bd_get();
        const int X0 = (wide_bd_x(&bd,x0)+dx)*s, X1 = (wide_bd_x(&bd,x1)+dx)*s, X2 = (wide_bd_x(&bd,x2)+dx)*s;
        WkCmd *c = wk_begin();
        if (c) {
            c->kind = WK_FLAT_TRI; c->t = wt; rstate_globals(&c->st);
            int *p = c->p;
            p[0] = X0; p[1] = y0*s; p[2] = X1; p[3] = y1*s; p[4] = X2; p[5] = y2*s; p[6] = color;
            wk_commit();
        } else {
            raster_flat_triangle(&wt, X0, y0*s, X1, y1*s, X2, y2*s, color);
        }
    }
}
''')
    t = reemplazar_funcion(t, 'void sw_draw_gouraud_triangle(int x0, int y0, uint16_t c0,', '''void sw_draw_gouraud_triangle(int x0, int y0, uint16_t c0,
                              int x1, int y1, uint16_t c1,
                              int x2, int y2, uint16_t c2) {
    wk_hazard_clip();
    RTarget n = rt_native();
    raster_gouraud_triangle(&n, x0, y0, c0, x1, y1, c1, x2, y2, c2);
    if (g_hr) {
        int s = g_scale;
        RTarget hr = rt_hires();
        raster_gouraud_triangle(&hr, x0*s, y0*s, c0, x1*s, y1*s, c1, x2*s, y2*s, c2);
    }
    if (g_wide_cur) {
        int s = g_scale, dx = wide_dx();
        RTarget wt = rt_wide();
        WideBd bd = wide_bd_get();
        const int X0 = (wide_bd_x(&bd,x0)+dx)*s, X1 = (wide_bd_x(&bd,x1)+dx)*s, X2 = (wide_bd_x(&bd,x2)+dx)*s;
        WkCmd *c = wk_begin();
        if (c) {
            c->kind = WK_GOU_TRI; c->t = wt; rstate_globals(&c->st);
            int *p = c->p;
            p[0] = X0; p[1] = y0*s; p[2] = c0; p[3] = X1; p[4] = y1*s; p[5] = c1;
            p[6] = X2; p[7] = y2*s; p[8] = c2;
            wk_commit();
        } else {
            raster_gouraud_triangle(&wt, X0, y0*s, c0, X1, y1*s, c1, X2, y2*s, c2);
        }
    }
}
''')
    t = reemplazar_funcion(t, 'void sw_draw_textured_triangle(int x0, int y0, int u0, int v0,', '''void sw_draw_textured_triangle(int x0, int y0, int u0, int v0,
                               int x1, int y1, int u1, int v1,
                               int x2, int y2, int u2, int v2,
                               uint16_t clut_x, uint16_t clut_y,
                               uint16_t texpage) {
    int64_t area2 = (int64_t)(x1 - x0) * (int64_t)(y2 - y0)
                  - (int64_t)(x2 - x0) * (int64_t)(y1 - y0);
    if (area2 == 0) return;

    if (g_texture_filter) {
        int xs[3] = {x0,x1,x2}, ys[3] = {y0,y1,y2};
        int us[3] = {u0,u1,u2}, vs[3] = {v0,v1,v2};
        sw_tri_uv_limits(xs, ys, us, vs);
    }

    wk_hazard_clip();
    RTarget n = rt_native();
    raster_textured_triangle(&n, x0, y0, u0, v0, x1, y1, u1, v1,
                             x2, y2, u2, v2, clut_x, clut_y, texpage);
    if (g_hr) {
        int s = g_scale;
        RTarget hr = rt_hires();
        raster_textured_triangle(&hr, x0*s, y0*s, u0, v0,
                                 x1*s, y1*s, u1, v1,
                                 x2*s, y2*s, u2, v2, clut_x, clut_y, texpage);
    }
    if (g_wide_cur) {
        int s = g_scale, dx = wide_dx();
        RTarget wt = rt_wide();
        WideBd bd = wide_bd_get();
        const int X0 = (wide_bd_x(&bd,x0)+dx)*s, X1 = (wide_bd_x(&bd,x1)+dx)*s, X2 = (wide_bd_x(&bd,x2)+dx)*s;
        WkCmd *c = wk_begin();
        if (c) {
            c->kind = WK_TEX_TRI; c->t = wt; rstate_globals(&c->st);
            int *p = c->p;
            p[0] = X0; p[1] = y0*s; p[2] = u0; p[3] = v0; p[4] = X1; p[5] = y1*s; p[6] = u1; p[7] = v1;
            p[8] = X2; p[9] = y2*s; p[10] = u2; p[11] = v2; p[12] = clut_x; p[13] = clut_y; p[14] = texpage;
            wk_note_tex(&c->st, texpage, clut_x, clut_y, min3_i(u0, u1, u2), max3_i(u0, u1, u2),
                        min3_i(v0, v1, v2), max3_i(v0, v1, v2));
            wk_commit();
        } else {
            raster_textured_triangle(&wt, X0, y0*s, u0, v0, X1, y1*s, u1, v1,
                                     X2, y2*s, u2, v2, clut_x, clut_y, texpage);
        }
    }
}
''')
    t = reemplazar_funcion(t, 'void sw_draw_shaded_textured_triangle(int x0, int y0, int u0, int v0,', '''void sw_draw_shaded_textured_triangle(int x0, int y0, int u0, int v0,
                                      uint32_t color0,
                                      int x1, int y1, int u1, int v1,
                                      uint32_t color1,
                                      int x2, int y2, int u2, int v2,
                                      uint32_t color2,
                                      uint16_t clut_x, uint16_t clut_y,
                                      uint16_t texpage, int raw_texture) {
    int64_t area2 = (int64_t)(x1 - x0) * (int64_t)(y2 - y0)
                  - (int64_t)(x2 - x0) * (int64_t)(y1 - y0);
    if (area2 == 0) return;

    if (g_texture_filter) {
        int xs[3] = {x0,x1,x2}, ys[3] = {y0,y1,y2};
        int us[3] = {u0,u1,u2}, vs[3] = {v0,v1,v2};
        sw_tri_uv_limits(xs, ys, us, vs);
    }

    int r0, g0, b0, r1, g1, b1, r2, g2, b2;
    color24_to_mod(color0, &r0, &g0, &b0);
    color24_to_mod(color1, &r1, &g1, &b1);
    color24_to_mod(color2, &r2, &g2, &b2);

    wk_hazard_clip();
    RTarget n = rt_native();
    raster_shaded_textured_triangle(&n,
        x0, y0, u0, v0, r0, g0, b0,
        x1, y1, u1, v1, r1, g1, b1,
        x2, y2, u2, v2, r2, g2, b2,
        clut_x, clut_y, texpage, raw_texture);
    if (g_hr) {
        int s = g_scale;
        RTarget hr = rt_hires();
        raster_shaded_textured_triangle(&hr,
            x0*s, y0*s, u0, v0, r0, g0, b0,
            x1*s, y1*s, u1, v1, r1, g1, b1,
            x2*s, y2*s, u2, v2, r2, g2, b2,
            clut_x, clut_y, texpage, raw_texture);
    }
    if (g_wide_cur) {
        int s = g_scale, dx = wide_dx();
        RTarget wt = rt_wide();
        WideBd bd = wide_bd_get();
        const int X0 = (wide_bd_x(&bd,x0)+dx)*s, X1 = (wide_bd_x(&bd,x1)+dx)*s, X2 = (wide_bd_x(&bd,x2)+dx)*s;
        WkCmd *c = wk_begin();
        if (c) {
            c->kind = WK_STEX_TRI; c->t = wt; rstate_globals(&c->st);
            int *p = c->p;
            p[0] = X0; p[1] = y0*s; p[2] = u0; p[3] = v0; p[4] = r0; p[5] = g0; p[6] = b0;
            p[7] = X1; p[8] = y1*s; p[9] = u1; p[10] = v1; p[11] = r1; p[12] = g1; p[13] = b1;
            p[14] = X2; p[15] = y2*s; p[16] = u2; p[17] = v2; p[18] = r2; p[19] = g2; p[20] = b2;
            p[21] = clut_x; p[22] = clut_y; p[23] = texpage; p[24] = raw_texture;
            wk_note_tex(&c->st, texpage, clut_x, clut_y, min3_i(u0, u1, u2), max3_i(u0, u1, u2),
                        min3_i(v0, v1, v2), max3_i(v0, v1, v2));
            wk_commit();
        } else {
            raster_shaded_textured_triangle(&wt,
                X0, y0*s, u0, v0, r0, g0, b0,
                X1, y1*s, u1, v1, r1, g1, b1,
                X2, y2*s, u2, v2, r2, g2, b2,
                clut_x, clut_y, texpage, raw_texture);
        }
    }
}
''')
    t = reemplazar_funcion(t, 'void sw_draw_flat_rect(int x, int y, int w, int h, uint16_t color) {', '''void sw_draw_flat_rect(int x, int y, int w, int h, uint16_t color) {
    wk_hazard_clip();
    RTarget n = rt_native();
    raster_flat_rect(&n, x, y, w, h, color);
    if (g_hr) {
        int s = g_scale;
        RTarget hr = rt_hires();
        raster_flat_rect(&hr, x*s, y*s, w*s, h*s, color);
    }
    if (g_wide_cur) {
        int s = g_scale, dx = wide_dx();
        RTarget wt = rt_wide();
        /* Full-screen 2D overlay (pause gray-filter / load fade): a flat rect
         * spanning the whole 4:3 framebuffer must cover the whole wide surface
         * too, else the revealed 16:9 margins are left undimmed/unfaded. Detect
         * a rect whose native screen-X span (x - base) covers [0, native_w) and
         * extend its wide pass across the full surface; every other rect mirrors
         * 1:1 as before. native_w = the 4:3 framebuffer width (g_wide_w less the
         * per-side reveal on both sides); g_wide_cur_base is its VRAM left edge.
         * Only runs in native-wide (g_wide_cur != NULL), so 4:3 is unaffected. */
        int native_w = g_wide_w - 2 * g_wide_off;
        int lx = x - g_wide_cur_base, rx = x + w - g_wide_cur_base;
        WideBd bd = wide_bd_get();
        int RX, RW;
        if (native_w > 0 && lx <= 0 && rx >= native_w) { RX = 0; RW = g_wide_w*s; }
        else if (bd.on) {
            int xl = wide_bd_x(&bd, x), xr = wide_bd_x(&bd, x + w);
            RX = (xl+dx)*s; RW = (xr-xl)*s;
        } else { RX = (x+dx)*s; RW = w*s; }
        WkCmd *c = wk_begin();
        if (c) {
            c->kind = WK_FLAT_RECT; c->t = wt; rstate_globals(&c->st);
            int *p = c->p;
            p[0] = RX; p[1] = y*s; p[2] = RW; p[3] = h*s; p[4] = color;
            wk_commit();
        } else {
            raster_flat_rect(&wt, RX, y*s, RW, h*s, color);
        }
    }
}
''')
    t = reemplazar_funcion(t, 'void sw_draw_textured_rect(int x, int y, int w, int h,', '''void sw_draw_textured_rect(int x, int y, int w, int h,
                           int u, int v,
                           uint16_t clut_x, uint16_t clut_y,
                           uint16_t texpage) {
    if (g_texture_filter) sw_rect_uv_limits(u, v, u + w, v + h);
    wk_hazard_clip();
    RTarget n = rt_native();
    raster_textured_rect(&n, x, y, w, h, u, v, clut_x, clut_y, texpage);
    if (g_hr) {
        int s = g_scale;
        RTarget hr = rt_hires();
        raster_textured_rect(&hr, x*s, y*s, w*s, h*s, u, v, clut_x, clut_y, texpage);
    }
    if (g_wide_cur) {
        int s = g_scale, dx = wide_dx();
        RTarget wt = rt_wide();
        WideBd bd = wide_bd_get();
        WkCmd *c = wk_begin();
        if (bd.on) {
            /* Stretch about screen centre: widen the destination span and map the
             * native texel footprint across it via the SCALED rasterizer (the
             * 1:1 sampler would TILE a widened rect instead of stretching it). */
            int xl = wide_bd_x(&bd, x), xr = wide_bd_x(&bd, x + w);
            if (c) {
                c->kind = WK_TEX_RECT_SCALED; c->t = wt; rstate_globals(&c->st);
                int *p = c->p;
                p[0] = (xl+dx)*s; p[1] = y*s; p[2] = (xr-xl)*s; p[3] = h*s;
                p[4] = u; p[5] = v; p[6] = u + w; p[7] = v + h; p[8] = clut_x; p[9] = clut_y; p[10] = texpage;
                wk_note_tex(&c->st, texpage, clut_x, clut_y, u, u + w, v, v + h);
                wk_commit();
            } else {
                raster_textured_rect_scaled(&wt, (xl+dx)*s, y*s, (xr-xl)*s, h*s,
                                            u, v, u + w, v + h, clut_x, clut_y, texpage);
            }
        } else if (c) {
            c->kind = WK_TEX_RECT; c->t = wt; rstate_globals(&c->st);
            int *p = c->p;
            p[0] = (x+dx)*s; p[1] = y*s; p[2] = w*s; p[3] = h*s; p[4] = u; p[5] = v;
            p[6] = clut_x; p[7] = clut_y; p[8] = texpage;
            wk_note_tex(&c->st, texpage, clut_x, clut_y, u, u + w - 1, v, v + h - 1);
            wk_commit();
        } else {
            raster_textured_rect(&wt, (x+dx)*s, y*s, w*s, h*s, u, v, clut_x, clut_y, texpage);
        }
    }
}
''')
    t = insertar_al_principio(t, 'void sw_wide_emit_tile(int band_y, int x, int y, int u, int v,',
                              '    wk_drain();   /* inline wide-surface write: keep wide writes ordered */\n')
    t = reemplazar_funcion(t, 'void sw_draw_textured_rect_scaled(int x, int y, int w, int h,', '''void sw_draw_textured_rect_scaled(int x, int y, int w, int h,
                                  int u0, int v0, int u1, int v1,
                                  uint16_t clut_x, uint16_t clut_y,
                                  uint16_t texpage) {
    if (w <= 0 || h <= 0) return;
    if (g_texture_filter) sw_rect_uv_limits(u0, v0, u1, v1);
    wk_hazard_clip();
    RTarget n = rt_native();
    raster_textured_rect_scaled(&n, x, y, w, h, u0, v0, u1, v1,
                                clut_x, clut_y, texpage);
    if (g_hr) {
        int s = g_scale;
        RTarget hr = rt_hires();
        /* Footprint scales by s; the destination span widens so the texel
         * step stays per-native-pixel. */
        raster_textured_rect_scaled(&hr, x*s, y*s, w*s, h*s, u0, v0, u1, v1,
                                    clut_x, clut_y, texpage);
    }
    if (g_wide_cur) {
        int s = g_scale, dx = wide_dx();
        RTarget wt = rt_wide();
        WideBd bd = wide_bd_get();
        int xl = wide_bd_x(&bd, x), xr = wide_bd_x(&bd, x + w);
        WkCmd *c = wk_begin();
        if (c) {
            c->kind = WK_TEX_RECT_SCALED; c->t = wt; rstate_globals(&c->st);
            int *p = c->p;
            p[0] = (xl+dx)*s; p[1] = y*s; p[2] = (xr-xl)*s; p[3] = h*s;
            p[4] = u0; p[5] = v0; p[6] = u1; p[7] = v1; p[8] = clut_x; p[9] = clut_y; p[10] = texpage;
            wk_note_tex(&c->st, texpage, clut_x, clut_y, min_i(u0, u1), max_i(u0, u1),
                        min_i(v0, v1), max_i(v0, v1));
            wk_commit();
        } else {
            raster_textured_rect_scaled(&wt, (xl+dx)*s, y*s, (xr-xl)*s, h*s, u0, v0, u1, v1,
                                        clut_x, clut_y, texpage);
        }
    }
}
''')
    t = reemplazar_funcion(t, 'void sw_draw_line(int x0, int y0, int x1, int y1, uint16_t color) {', '''void sw_draw_line(int x0, int y0, int x1, int y1, uint16_t color) {
    wk_hazard_clip();
    /* The wide pass of a line runs on the worker as one command (same Bresenham walk). */
    WkCmd *c = g_wide_cur ? wk_begin() : NULL;
    if (c) {
        c->kind = WK_LINE; c->t = rt_wide(); rstate_globals(&c->st);
        int *p = c->p;
        p[0] = wide_dx(); p[1] = x0; p[2] = y0; p[3] = x1; p[4] = y1; p[5] = color;
        wk_commit();
    }
    RTarget n = rt_native();
    int dx = abs(x1 - x0);
    int dy = -abs(y1 - y0);
    int sx = (x0 < x1) ? 1 : -1;
    int sy = (y0 < y1) ? 1 : -1;
    int err = dx + dy;

    for (;;) {
        put_opaque(&n, x0, y0, color);
        if (g_hr) hr_put_block_opaque(x0, y0, color);
        if (!c) wide_put_block_opaque(x0, y0, color);

        if (x0 == x1 && y0 == y1) break;

        int e2 = 2 * err;
        if (e2 >= dy) { err += dy; x0 += sx; }
        if (e2 <= dx) { err += dx; y0 += sy; }
    }
}
''')
    t = reemplazar_funcion(t, 'void sw_draw_shaded_line(int x0, int y0, uint16_t c0,', '''void sw_draw_shaded_line(int x0, int y0, uint16_t c0,
                         int x1, int y1, uint16_t c1) {
    wk_hazard_clip();
    /* The wide pass of a line runs on the worker as one command (same walk and colors). */
    WkCmd *wc = g_wide_cur ? wk_begin() : NULL;
    if (wc) {
        wc->kind = WK_SLINE; wc->t = rt_wide(); rstate_globals(&wc->st);
        int *p = wc->p;
        p[0] = wide_dx(); p[1] = x0; p[2] = y0; p[3] = c0; p[4] = x1; p[5] = y1; p[6] = c1;
        wk_commit();
    }
    RTarget n = rt_native();
    int dx = abs(x1 - x0);
    int dy = -abs(y1 - y0);
    int sx = (x0 < x1) ? 1 : -1;
    int sy = (y0 < y1) ? 1 : -1;
    int err = dx + dy;

    /* Total steps for interpolation */
    int total = max_i(abs(x1 - x0), abs(y1 - y0));
    if (total == 0) total = 1;

    /* Extract 5-bit color channels */
    int r0 = c0 & 0x1F, g0 = (c0 >> 5) & 0x1F, b0 = (c0 >> 10) & 0x1F;
    int r1 = c1 & 0x1F, g1 = (c1 >> 5) & 0x1F, b1 = (c1 >> 10) & 0x1F;

    int step = 0;
    for (;;) {
        int r = r0 + (r1 - r0) * step / total;
        int g = g0 + (g1 - g0) * step / total;
        int b = b0 + (b1 - b0) * step / total;
        uint16_t color = (uint16_t)(r | (g << 5) | (b << 10));
        put_opaque(&n, x0, y0, color);
        if (g_hr) hr_put_block_opaque(x0, y0, color);
        if (!wc) wide_put_block_opaque(x0, y0, color);

        if (x0 == x1 && y0 == y1) break;

        int e2 = 2 * err;
        if (e2 >= dy) { err += dy; x0 += sx; }
        if (e2 <= dx) { err += dx; y0 += sy; }
        step++;
    }
}
''')
    # escrituras de VRAM fuera de un dibujo: esperar si una orden pendiente lee ahí
    t = insertar_al_principio(t, 'void sw_fill_rect(int x, int y, int w, int h, uint16_t color) {',
                              '    wk_hazard_wrapped(x, y, w, h);   /* pending wide commands may read here */\n')
    t = insertar_al_principio(t, 'void sw_copy_rect(int src_x, int src_y, int dst_x, int dst_y, int w, int h) {',
                              '    wk_hazard_wrapped(dst_x, dst_y, w, h);   /* pending wide commands may read here */\n')
    t = insertar_al_principio(t, 'void sw_vram_write(int x, int y, uint16_t pixel) {',
                              '    wk_hazard_wrapped(x, y, 1, 1);   /* pending wide commands may read here */\n')
    t = insertar_al_principio(t, 'void sw_vram_transfer_in(int x, int y, int w, int h, const uint16_t *data) {',
                              '    wk_hazard_wrapped(x, y, w, h);   /* pending wide commands may read here */\n')
    t = insertar_al_principio(t, 'void sw_renderer_init(uint16_t *vram) {', '    wk_drain();\n')
    t = insertar_al_principio(t, 'void sw_renderer_set_scale(int scale) {', '    wk_drain();\n')
    t = insertar_al_principio(t, 'void sw_wide_configure(int wide_w, int offset) {',
                              '    if (wide_w <= 0 || wide_w != g_wide_w) wk_drain();   /* surfaces may be freed */\n')
    t = reemplazar_funcion(t, 'void sw_wide_clear(int base_x, int y, int h, uint16_t color) {', '''void sw_wide_clear(int base_x, int y, int h, uint16_t color) {
    uint16_t *surf = wide_surf_for(base_x);
    if (!surf) return;
    int s = g_scale;
    int W = g_wide_w * s;
    int H = VRAM_HEIGHT * s;
    int y0 = y * s, y1 = (y + h) * s;
    if (y0 < 0) y0 = 0;
    if (y1 > H) y1 = H;
    WkCmd *c = wk_begin();   /* ordered with the queued wide draws */
    if (c) {
        c->kind = WK_FILL_ROWS; c->t.buf = surf; c->t.w = W; c->t.h = H;
        c->p[0] = y0; c->p[1] = y1; c->p[2] = color;
        wk_commit();
        return;
    }
    for (int row = y0; row < y1; row++) {
        uint16_t *dst = surf + (size_t)row * W;
        for (int col = 0; col < W; col++) dst[col] = color;
    }
}
''')
    t = reemplazar_funcion(t, 'void sw_wide_clear_margins(int base_x, int y, int h, uint16_t color, int sides) {', '''void sw_wide_clear_margins(int base_x, int y, int h, uint16_t color, int sides) {
    uint16_t *surf = wide_surf_for(base_x);
    if (!surf) return;
    int s = g_scale;
    int W = g_wide_w * s;
    int H = VRAM_HEIGHT * s;
    int margin = g_wide_off * s;
    int y0 = y * s, y1 = (y + h) * s;
    if (margin <= 0 || margin * 2 >= W) return;
    if (y0 < 0) y0 = 0;
    if (y1 > H) y1 = H;
    WkCmd *c = wk_begin();   /* ordered with the queued wide draws */
    if (c) {
        c->kind = WK_FILL_MARGINS; c->t.buf = surf; c->t.w = W; c->t.h = H;
        c->p[0] = y0; c->p[1] = y1; c->p[2] = color; c->p[3] = margin; c->p[4] = sides;
        wk_commit();
        return;
    }
    for (int row = y0; row < y1; row++) {
        uint16_t *dst = surf + (size_t)row * W;
        if (sides & 1) for (int col = 0; col < margin; col++) dst[col] = color;
        if (sides & 2) for (int col = W - margin; col < W; col++) dst[col] = color;
    }
}
''')
    t = insertar_al_principio(t, 'int sw_render_wide_display(uint32_t *out_pixels, int out_pitch, int base_x,',
                              '    wk_drain();   /* the worker may still be drawing this surface */\n')
    t = insertar_al_principio(t, 'int sw_wide_dump_full(uint32_t *out, int cap_pixels, int *ow, int *oh, int base_x) {',
                              '    wk_drain();   /* the worker may still be drawing this surface */\n')
    t = t.rstrip('\n') + '''

/* Recompilaciones (2026-10-03): native-wide worker sync points for gpu.c, which writes VRAM
 * directly (CPU->VRAM uploads pixel by pixel, resets, savestate loads). */
void sw_wide_sync(void) { wk_drain(); }
void sw_wide_hazard_rect(int x, int y, int w, int h) { wk_hazard_wrapped(x, y, w, h); }
/* Diagnostics for the [FPS] line: commands queued to the worker, and emu-thread waits on it. */
unsigned long long sw_wide_worker_cmds(void) { return wk_cmds; }
unsigned long long sw_wide_worker_waits(void) { return wk_waits; }
'''
    return t


GPU_CAMBIOS = [
    ('''    vram_write_w = (w == 0) ? 0x400 : (uint16_t)w;
    vram_write_h = (h == 0) ? 0x200 : (uint16_t)h;
''', '''    vram_write_w = (w == 0) ? 0x400 : (uint16_t)w;
    vram_write_h = (h == 0) ? 0x200 : (uint16_t)h;
    /* Recompilaciones (2026-10-03): the upload writes VRAM directly, pixel by pixel; the
     * software renderer's native-wide worker may still read texels there. */
    { extern void sw_wide_hazard_rect(int, int, int, int);
      sw_wide_hazard_rect((int)vram_write_x, (int)vram_write_y, (int)vram_write_w, (int)vram_write_h); }
'''),
    ('''static void gpu_reset_state(int clear_vram) {
    if (clear_vram) {''', '''static void gpu_reset_state(int clear_vram) {
    { extern void sw_wide_sync(void); sw_wide_sync(); }   /* Recompilaciones: native-wide worker */
    if (clear_vram) {'''),
    ('''int gpu_snapshot_read(const uint8_t *p, uint32_t len){ if(len!=gpu_snapshot_bytes()) return 0;''',
     '''int gpu_snapshot_read(const uint8_t *p, uint32_t len){ if(len!=gpu_snapshot_bytes()) return 0;
    { extern void sw_wide_sync(void); sw_wide_sync(); }   /* Recompilaciones: native-wide worker */'''),
    ('''uint16_t* gpu_get_vram_ptr(void){ return vram; }''',
     '''uint16_t* gpu_get_vram_ptr(void){
    extern void sw_wide_sync(void); sw_wide_sync();   /* Recompilaciones: callers write VRAM (state loads) */
    return vram; }'''),
]


# main.cpp (la línea [FPS] de parche_fases.py): órdenes encoladas al hilo y esperas del hilo del emulador por segundo
MAIN_CAMBIOS = [
    (r'''extern "C" int psx_exec_phase(void);
''', r'''extern "C" int psx_exec_phase(void);
extern "C" unsigned long long sw_wide_worker_cmds(void);    /* Recompilaciones: native-wide worker */
extern "C" unsigned long long sw_wide_worker_waits(void);
'''),
    (r'''                std::fprintf(stderr, "[FPS] game: %.1f fps (%.2fx) | frames: %llu | phase other %.2f interp %.2f "
                             "native %.2f static %.2f gp0 %.2f (n=%u)\n",
                             fps, speed, (unsigned long long)s_frame_count,
                             c[0] / d, c[1] / d, c[2] / d, c[3] / d, c[4] / d, n);
''', r'''                static unsigned long long wk_last_cmds, wk_last_waits;   /* native-wide worker, last second */
                const unsigned long long wk_c = sw_wide_worker_cmds(), wk_w = sw_wide_worker_waits();
                std::fprintf(stderr, "[FPS] game: %.1f fps (%.2fx) | frames: %llu | phase other %.2f interp %.2f "
                             "native %.2f static %.2f gp0 %.2f (n=%u) | wide worker %llu cmds %llu waits\n",
                             fps, speed, (unsigned long long)s_frame_count,
                             c[0] / d, c[1] / d, c[2] / d, c[3] / d, c[4] / d, n,
                             wk_c - wk_last_cmds, wk_w - wk_last_waits);
                wk_last_cmds = wk_c; wk_last_waits = wk_w;
'''),
]


def escribir(ruta, eol, texto):
    with open(ruta + '.tmp', 'wb') as f:
        f.write(texto.replace('\n', eol).encode('utf-8'))
    os.replace(ruta + '.tmp', ruta)


def leer(ruta):
    t = open(ruta, 'rb').read().decode('utf-8')
    return ('\r\n' if '\r\n' in t else '\n'), t.replace('\r\n', '\n')


def main():
    hechos = []
    pendientes = []                     # (ruta, eol, texto): todo o nada, se escribe al final
    sw = os.path.join(R, 'gpu_sw_renderer.c')
    eol, t = leer(sw)
    if MARCA in t:
        hechos.append('gpu_sw_renderer.c: ya estaba')
    else:
        if 'fast nearest-filter span paths' in t:
            raise SystemExit('gpu_sw_renderer.c lleva parche_raster_rapido.py: restaura el original antes')
        pendientes.append((sw, eol, parchear_renderer(t)))
        hechos.append('gpu_sw_renderer.c: caminos rápidos y pasada ancha en un segundo hilo')
    if not SOLO_SW:
        for nombre, firma, cambios, que in (
                ('gpu.c', 'sw_wide_hazard_rect((int)vram_write_x', GPU_CAMBIOS,
                 'sincronización en las cargas CPU->VRAM, el reinicio y los estados'),
                ('main.cpp', 'sw_wide_worker_cmds()', MAIN_CAMBIOS,
                 'la línea [FPS] cuenta las órdenes del hilo ancho y las esperas')):
            ruta = os.path.join(R, nombre)
            e, g = leer(ruta)
            if firma in g:
                hechos.append(f'{nombre}: ya estaba')
                continue
            for viejo, nuevo_g in cambios:
                g = sustituir(g, viejo, nuevo_g)
            pendientes.append((ruta, e, g))
            hechos.append(f'{nombre}: {que}')
    for ruta, e, texto in pendientes:
        escribir(ruta, e, texto)
    print('\n'.join(hechos))


if __name__ == '__main__':
    main()
