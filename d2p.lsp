;;; d2p.lsp - plot the current drawing's model space to a single PDF page.
;;; dwg_to_pdf.py pastes this into the core console script (accoreconsole.exe)
;;; with comments and blank lines stripped - so never put a semicolon in a string.
;;;
;;; (d2p-plot out ctb paper)
;;;   out   - full path of the PDF to write (forward slashes)
;;;   ctb   - plot style table, e.g. "monochrome.ctb"; "" = plot in color, no style table
;;;   paper - a DWG To PDF.pc3 paper name, or "AUTO" to pick the smallest sheet the
;;;           drawing extents fit on (assumes the title block is drawn 1:1 in inches;
;;;           anything that fits nothing falls back to ARCH D). Always plotted "Fit".

(setq d2p-sizes
  ;; smallest first - first match wins
  '(("ANSI full bleed A (11.00 x 8.50 Inches)"  11.0  8.5)
    ("ANSI full bleed B (17.00 x 11.00 Inches)" 17.0 11.0)
    ("ANSI full bleed C (22.00 x 17.00 Inches)" 22.0 17.0)
    ("ARCH full bleed C (24.00 x 18.00 Inches)" 24.0 18.0)
    ("ANSI full bleed D (34.00 x 22.00 Inches)" 34.0 22.0)
    ("ARCH full bleed D (36.00 x 24.00 Inches)" 36.0 24.0)
    ("ANSI full bleed E (44.00 x 34.00 Inches)" 44.0 34.0)
    ("ARCH full bleed E (48.00 x 36.00 Inches)" 48.0 36.0)))

(defun d2p-plot (out ctb paper / mn mx w h lw sw orient)
  (setq mn (getvar "EXTMIN")
        mx (getvar "EXTMAX")
        w  (- (car mx) (car mn))
        h  (- (cadr mx) (cadr mn))
        lw (max w h)
        sw (min w h)
        orient (if (>= w h) "_L" "_P"))
  (if (= paper "AUTO")
    (progn
      (setq paper nil)
      (foreach s d2p-sizes
        (if (and (null paper)
                 (<= lw (* 1.02 (cadr s)))
                 (<= sw (* 1.02 (caddr s))))
          (setq paper (car s))))
      (if (null paper) (setq paper "ARCH full bleed D (36.00 x 24.00 Inches)"))))
  (princ (strcat "\nD2P-PAPER=" paper "\n"))
  (if (= ctb "")
    (command "_.-PLOT" "_Y" "" "DWG To PDF.pc3" paper "_I" orient "_N"
             "_E" "_F" "_C" "_N" "_Y" "_A" out "_N" "_Y")
    (command "_.-PLOT" "_Y" "" "DWG To PDF.pc3" paper "_I" orient "_N"
             "_E" "_F" "_C" "_Y" ctb "_Y" "_A" out "_N" "_Y"))
  (princ))
