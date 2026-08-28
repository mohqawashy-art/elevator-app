"""اختبارات تحويل الأسماء العربية إلى لاتيني."""

from liftcore_translit import arabic_to_latin


def test_common_names_and_districts():
    assert arabic_to_latin('محمد') == 'Mohamed'
    assert arabic_to_latin('عبد العزيز') == 'Abdulaziz'
    assert arabic_to_latin('محمد عبد العزيز') == 'Mohamed Abdulaziz'
    assert arabic_to_latin('العزيزية') == 'Al-Azizia'
    assert arabic_to_latin('مكة') == 'Makkah'


def test_building_label_translation():
    assert arabic_to_latin('برج الياسمين') == 'Yasmin Tower'
    assert arabic_to_latin('برج المملكة') == 'Kingdom Tower'
    assert arabic_to_latin('مجمع السلام') == 'Salam Complex'
    assert arabic_to_latin('فيلا النخيل') == 'Nakheel Villa'
    assert arabic_to_latin('برج سكني الياسمين') == 'Yasmin Residential Tower'
