import hashlib
import unittest
from tehnet.pac import Pac,FOOTER_SIZE,RECORD_SIZE,encode_config,put_field,config_values,replace_values

def synthetic_pac():
    text=b'export TZ_USERNAME="owner-example"\nexport TZ_PASSWD="PROMPT_ON_INSTALL"\nexport TZ_BAND_PREF="unchanged-example"\n'
    parts=[(b'config',encode_config(text)),(b'firewall',b'[]'),(b'reservedip',b'')]
    footer=bytearray(FOOTER_SIZE);put_field(footer,0,b'3');put_field(footer,FOOTER_SIZE-96,str(FOOTER_SIZE).encode())
    offset=0
    for i,(name,content) in enumerate(parts):
        base=32+i*RECORD_SIZE
        for position,value,width in [(0,name,32),(32,b'P19H',64),(96,str(len(content)).encode(),32),
             (128,str(offset).encode(),32),(160,hashlib.md5(content).hexdigest().encode(),64),(224,name+b'.txt',224)]:
            put_field(footer,base+position,value,width)
        offset+=len(content)
    return b''.join(content for _,content in parts)+bytes(footer)

class PacTests(unittest.TestCase):
    def test_roundtrip_and_only_requested_literal_value_changes(self):
        raw=synthetic_pac();pac=Pac.parse(raw);self.assertEqual(pac.pack(),raw)
        before=config_values(pac.text());other=[entry.content for entry in pac.entries[1:]]
        pac.replace_text(replace_values(pac.text(),{'TZ_USERNAME':'example-new'}))
        rebuilt=Pac.parse(pac.pack());after=config_values(rebuilt.text())
        self.assertEqual(after['TZ_BAND_PREF'],before['TZ_BAND_PREF'])
        self.assertEqual([entry.content for entry in rebuilt.entries[1:]],other)
    def test_corrupt_component_and_inner_checksum_rejected(self):
        raw=bytearray(synthetic_pac());raw[0]^=1
        with self.assertRaises(ValueError):Pac.parse(bytes(raw))
        pac=Pac.parse(synthetic_pac());content=bytearray(pac.config_entry().content);content[-1]^=1
        pac.config_entry().content=bytes(content)
        with self.assertRaisesRegex(ValueError,'checksum'):Pac.parse(pac.pack())
    def test_unknown_key_and_shell_interpolation_rejected(self):
        text=Pac.parse(synthetic_pac()).text()
        for change in [{'TZ_UNKNOWN':'x'},{'TZ_USERNAME':'$(x)'},{'TZ_USERNAME':'bad\nvalue'}]:
            with self.assertRaises(ValueError):replace_values(text,change)

if __name__=='__main__':unittest.main()
