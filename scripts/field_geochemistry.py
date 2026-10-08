"""Clarify the mineral-exploration purpose of Field's geochemical workflow."""
PAIRS={
'ru':[
('План пунктов, отбор, журнал и подготовка партий проб.','Пробы для поисков полезных ископаемых по ореолам рассеивания.'),
('Геохимия: от плана к пробе.','Геохимические поиски: от плана к пробе.'),
('Отдельный процесс для донных осадков и потоков рассеяния.','Геохимический пробоотбор для поисков полезных ископаемых по ореолам рассеивания.')],
'en':[
('Plan sites, record sampling, review the journal and prepare batches.','Collect samples for mineral exploration using geochemical dispersion halos.'),
('Geochemistry from plan to sample.','Geochemical exploration from plan to sample.'),
('A dedicated workflow for stream sediments and drainage surveys.','Geochemical sampling for mineral exploration using dispersion halos.')]
}


def normalize_field_copy(text,lang):
 for before,after in PAIRS[lang]:text=text.replace(before,after)
 return text
