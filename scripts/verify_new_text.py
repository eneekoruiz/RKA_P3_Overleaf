import pypdf

reader = pypdf.PdfReader('overleaf_downloaded.pdf')
full_text = '\n'.join([p.extract_text() for p in reader.pages])

print('Contains self.timestamps:', 'timestamps' in full_text.lower())
print('Contains use_sim_time:', 'use_sim_time' in full_text.lower())
print('Contains Irakasleak emandako kodeak:', 'irakasleak emandako kodeak' in full_text.lower())
