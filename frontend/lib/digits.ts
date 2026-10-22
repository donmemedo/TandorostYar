const FA = "۰۱۲۳۴۵۶۷۸۹", AR = "٠١٢٣٤٥٦٧٨٩";

/** Persian and Arabic-Indic digits to ASCII. Phones and codes are typed on Persian keyboards. */
export const toLatin = (s: string) => s.replace(/[۰-۹]/g, (d) => String(FA.indexOf(d))).replace(/[٠-٩]/g, (d) => String(AR.indexOf(d)));

/** A whole number from whatever a person typed or pasted: any digit script, thousands separators and stray characters ignored, clamped to [0, max]. */
export const parseCount = (s: string, max: number) => Math.min(max, Number(toLatin(s).replace(/\D/g, "").slice(0, 9)) || 0);
