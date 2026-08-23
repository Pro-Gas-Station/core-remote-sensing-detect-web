# 检测报告 PDF
import os
import re
from datetime import datetime
from fpdf import FPDF
from fpdf.enums import XPos, YPos

WEB_FLASK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS_DIR = os.path.join(WEB_FLASK_DIR, 'data', 'fonts')
BUNDLED_REGULAR = os.path.join(FONTS_DIR, 'msyh.ttc')
BUNDLED_BOLD = os.path.join(FONTS_DIR, 'msyhbd.ttc')
TEAM_NAME_CN = '翊卫云瞳'
PDF_ENGINE_VERSION = 'fpdf2-light-gradient-v12'

# 品牌色（与网页经典红主题一致）
BRAND_RED = (228, 57, 60)
BRAND_RED_DARK = (200, 22, 35)
BRAND_ORANGE = (255, 122, 69)
TEXT_PRIMARY = (51, 51, 51)
TEXT_SECONDARY = (102, 102, 102)
TEXT_MUTED = (153, 153, 153)
TABLE_HEAD_FILL = (255, 235, 235)
TABLE_LABEL_FILL = (255, 248, 248)
TABLE_ROW_FILL = (255, 252, 252)
BORDER_COLOR = (232, 232, 232)


def _font_paths():
    """返回 (常规体, 加粗体) 路径，优先微软雅黑。"""
    win = os.environ.get('WINDIR', 'C:\\Windows')
    win_fonts = os.path.join(win, 'Fonts')
    candidates = [
        (BUNDLED_REGULAR, BUNDLED_BOLD),
        (os.path.join(win_fonts, 'msyh.ttc'), os.path.join(win_fonts, 'msyhbd.ttc')),
        (os.path.join(win_fonts, 'msyh.ttf'), os.path.join(win_fonts, 'msyhbd.ttf')),
        (os.path.join(win_fonts, 'simhei.ttf'), os.path.join(win_fonts, 'simhei.ttf')),
        (os.path.join(FONTS_DIR, 'simhei.ttf'), os.path.join(FONTS_DIR, 'simhei.ttf')),
    ]
    for regular, bold in candidates:
        if os.path.isfile(regular):
            if not os.path.isfile(bold):
                bold = regular
            return regular, bold
    return None, None


def _safe_text(value, max_len=200):
    text = str(value if value is not None else '')
    text = text.replace('\r', ' ').replace('\n', ' ')
    text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', text)
    if len(text) > max_len:
        text = text[: max_len - 3] + '...'
    return text or ' '


def _lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


class _ReportPDF(FPDF):
    def __init__(self):
        super().__init__()
        self._cn = False
        self._cn_bold = False
        regular, bold = _font_paths()
        if regular:
            try:
                self.add_font('cn', '', regular)
                self._cn = True
                if bold and bold != regular:
                    self.add_font('cn', 'B', bold)
                    self._cn_bold = True
                else:
                    self.add_font('cn', 'B', regular)
                    self._cn_bold = True
            except Exception:
                self._cn = False
                self._cn_bold = False

    def _content_width(self):
        w = self.w - self.l_margin - self.r_margin
        return w if w > 10 else 190

    def _set_body_font(self, size=11, bold=False):
        if self._cn:
            if bold and self._cn_bold:
                self.set_font('cn', 'B', size=size)
            else:
                self.set_font('cn', '', size=size)
        else:
            self.set_font('Helvetica', 'B' if bold else '', size=size)

    def _draw_h_gradient(self, x, y, w, h, c1, c2, steps=28):
        step_w = w / steps
        for i in range(steps):
            color = _lerp_color(c1, c2, i / max(steps - 1, 1))
            self.set_fill_color(*color)
            self.rect(x + i * step_w, y, step_w + 0.5, h, style='F')

    def _draw_shadow_text(self, x, y, w, h, text, size, bold=True, align='C', fg=(255, 255, 255), shadow=(110, 18, 18)):
        """模拟文字阴影（fpdf 无 text-shadow，叠印深色偏移字）。"""
        self._set_body_font(size, bold=bold)
        for ox, oy in ((0.35, 0.35), (0.6, 0.6)):
            self.set_text_color(*shadow)
            self.set_xy(x + ox, y + oy)
            self.cell(w, h, text, align=align, new_x=XPos.LMARGIN, new_y=YPos.TOP)
        self.set_text_color(*fg)
        self.set_xy(x, y)
        self.cell(w, h, text, align=align, new_x=XPos.LMARGIN, new_y=YPos.TOP)

    def _draw_header(self):
        x = self.l_margin
        w = self._content_width()
        y = self.get_y()
        band_h = 32

        # 整段橙红渐变页眉，标题直接叠在渐变上（无白色留白）
        self._draw_h_gradient(x, y, w, band_h, BRAND_ORANGE, BRAND_RED_DARK, steps=36)

        self._draw_shadow_text(
            x, y + 9, w, 9, TEAM_NAME_CN,
            size=18, bold=True, fg=(255, 255, 255), shadow=(110, 18, 18),
        )
        self._draw_shadow_text(
            x, y + 19, w, 7, '遥感影像目标检测报告',
            size=11, bold=True, fg=(255, 236, 236), shadow=(100, 16, 16),
        )

        self.set_text_color(*TEXT_PRIMARY)
        self.set_y(y + band_h + 8)

    def _section_title(self, text):
        x = self.l_margin
        w = self._content_width()
        y = self.get_y()
        bar_h = 9

        self._draw_h_gradient(x, y, w, bar_h, (255, 240, 238), (255, 225, 220), steps=12)
        self.set_xy(x + 3, y + 1.5)
        self._set_body_font(12, bold=True)
        self.set_text_color(*BRAND_RED_DARK)
        self.cell(w - 6, 6, text, new_x=XPos.LMARGIN, new_y=YPos.TOP)
        self.set_text_color(*TEXT_PRIMARY)
        self.set_y(y + bar_h + 4)

    def _draw_table(self, col_widths, rows, header=False, label_col=False, row_h=8):
        if not rows:
            return
        total_w = sum(col_widths)
        if total_w > self._content_width():
            scale = self._content_width() / total_w
            col_widths = [cw * scale for cw in col_widths]
        self.set_draw_color(*BORDER_COLOR)
        self.set_line_width(0.2)
        for row in rows:
            x0 = self.l_margin
            y0 = self.get_y()
            if y0 + row_h > self.h - 15:
                self.add_page()
                y0 = self.get_y()
            if header:
                self._set_body_font(10, bold=True)
                self.set_fill_color(*TABLE_HEAD_FILL)
                self.set_text_color(*BRAND_RED_DARK)
            else:
                self._set_body_font(9)
                self.set_text_color(*TEXT_PRIMARY)
            for i, txt in enumerate(row):
                cw = col_widths[i]
                align = 'C' if i == 0 else 'L'
                if not header and label_col and i == 0:
                    self.set_fill_color(*TABLE_LABEL_FILL)
                    self.set_text_color(*TEXT_SECONDARY)
                    self._set_body_font(9, bold=True)
                elif not header:
                    self.set_fill_color(*TABLE_ROW_FILL)
                    self.set_text_color(*TEXT_PRIMARY)
                    self._set_body_font(9)
                self.set_xy(x0, y0)
                self.multi_cell(
                    cw,
                    row_h,
                    _safe_text(txt, 120),
                    border=1,
                    align=align,
                    fill=True,
                    new_x=XPos.RIGHT,
                    new_y=YPos.TOP,
                )
                x0 += cw
            self.set_xy(self.l_margin, y0 + row_h)


def build_detection_pdf(username, model_name, detections, total, message=None):
    pdf = _ReportPDF()
    if not pdf._cn:
        raise RuntimeError('未找到可用的中文字体，请确保系统已安装微软雅黑，或将 msyh.ttc 放入 web-flask/data/fonts/ 目录')

    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf._draw_header()

    info_rows = [
        ['检测用户', _safe_text(username)],
        ['检测模型', _safe_text(model_name)],
        ['生成时间', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
        ['目标总数', str(total or 0)],
    ]
    if message:
        info_rows.append(['备注说明', _safe_text(message)])

    pdf._section_title('一、检测概要')
    info_widths = [36, pdf._content_width() - 36]
    pdf._draw_table(info_widths, info_rows, row_h=8, label_col=True)

    pdf.ln(5)
    pdf._section_title('二、检测明细')

    det_widths = [20, pdf._content_width() - 58, 38]
    detail_rows = []
    if detections:
        for i, d in enumerate(detections, 1):
            if not isinstance(d, dict):
                continue
            name = d.get('class_name_zh') or d.get('class_name', '')
            pct = d.get('percentage', d.get('confidence', ''))
            if isinstance(pct, float):
                pct = format(pct * 100, '.2f') + '%'
            detail_rows.append([str(i), _safe_text(name, 40), _safe_text(pct, 20)])
    if not detail_rows:
        detail_rows = [['—', '未检测到目标', '—']]

    pdf._draw_table(
        det_widths,
        [['序号', '目标类别', '置信度']],
        header=True,
        row_h=8,
    )
    pdf._draw_table(det_widths, detail_rows, row_h=7)

    pdf.ln(8)
    pdf._set_body_font(8)
    pdf.set_text_color(*TEXT_MUTED)
    pdf.cell(
        0, 5, TEAM_NAME_CN + ' · 遥感影像目标检测系统',
        align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )

    out = pdf.output(dest='S')
    if isinstance(out, str):
        return out.encode('latin-1')
    return bytes(out)
