type Translate = (key: string) => string;

const REALM_ALIAS_TO_KEY: Record<string, string> = {
  QI_REFINEMENT: 'QI_REFINEMENT',
  'QI REFINEMENT': 'QI_REFINEMENT',
  qi_refinement: 'QI_REFINEMENT',
  'qi refinement': 'QI_REFINEMENT',
  'Qi Refinement': 'QI_REFINEMENT',
  练气: 'QI_REFINEMENT',
  練氣: 'QI_REFINEMENT',
  練気: 'QI_REFINEMENT',

  FOUNDATION_ESTABLISHMENT: 'FOUNDATION_ESTABLISHMENT',
  'FOUNDATION ESTABLISHMENT': 'FOUNDATION_ESTABLISHMENT',
  foundation_establishment: 'FOUNDATION_ESTABLISHMENT',
  'foundation establishment': 'FOUNDATION_ESTABLISHMENT',
  'Foundation Establishment': 'FOUNDATION_ESTABLISHMENT',
  筑基: 'FOUNDATION_ESTABLISHMENT',
  築基: 'FOUNDATION_ESTABLISHMENT',

  CORE_FORMATION: 'CORE_FORMATION',
  'CORE FORMATION': 'CORE_FORMATION',
  core_formation: 'CORE_FORMATION',
  'core formation': 'CORE_FORMATION',
  'Core Formation': 'CORE_FORMATION',
  金丹: 'CORE_FORMATION',
  結丹: 'CORE_FORMATION',

  NASCENT_SOUL: 'NASCENT_SOUL',
  'NASCENT SOUL': 'NASCENT_SOUL',
  nascent_soul: 'NASCENT_SOUL',
  'nascent soul': 'NASCENT_SOUL',
  'Nascent Soul': 'NASCENT_SOUL',
  元婴: 'NASCENT_SOUL',
  元嬰: 'NASCENT_SOUL',
};

const STAGE_ALIAS_TO_KEY: Record<string, string> = {
  early_stage: 'early',
  'early stage': 'early',
  'Early Stage': 'early',
  early: 'early',
  前期: 'early',
  初期: 'early',

  middle_stage: 'middle',
  'middle stage': 'middle',
  'Middle Stage': 'middle',
  middle: 'middle',
  中期: 'middle',

  late_stage: 'late',
  'late stage': 'late',
  'Late Stage': 'late',
  late: 'late',
  後期: 'late',
  后期: 'late',
};

const TECHNIQUE_GRADE_KEYS = new Set(['LOWER', 'MIDDLE', 'UPPER']);
const ATTRIBUTE_KEYS = new Set(['GOLD', 'WOOD', 'WATER', 'FIRE', 'EARTH', 'ICE', 'WIND', 'DARK', 'THUNDER', 'EVIL']);

function translateByAlias(
  raw: string | number | null | undefined,
  aliasMap: Record<string, string>,
  translate: Translate,
  keyPrefix: string,
): string {
  if (raw === null || raw === undefined) return '';
  const trimmed = String(raw).trim();
  if (!trimmed) return '';
  const normalized = aliasMap[trimmed] ?? aliasMap[trimmed.toUpperCase()] ?? aliasMap[trimmed.toLowerCase()];
  return normalized ? translate(`${keyPrefix}.${normalized}`) : trimmed;
}

function getStageKeyFromLevel(level: number): 'early' | 'middle' | 'late' {
  if (level <= 0) return 'early';
  const stageIndex = Math.floor(((level - 1) % 30) / 10);
  if (stageIndex <= 0) return 'early';
  if (stageIndex === 1) return 'middle';
  return 'late';
}

export function humanizeIdentifier(raw: string | number | null | undefined): string {
  if (raw === null || raw === undefined) return '';
  const text = String(raw).trim();
  if (!text) return '';
  if (!/[_-]/.test(text) && !/[\p{Ll}\d]\p{Lu}/u.test(text)) return text;
  return text
    .replace(/^(?:content|item_label|item_verb)_/i, '')
    .replace(/([\p{Ll}\d])(\p{Lu})/gu, '$1 $2')
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .replace(/(^|\s)(\p{L})/gu, (_match, prefix: string, letter: string) => `${prefix}${letter.toLocaleUpperCase('pt-BR')}`);
}

export function formatGenderLabel(raw: string | null | undefined, translate: Translate): string {
  const value = String(raw ?? '').trim().toLowerCase();
  if (value === 'male' || value === '男') return translate('ui.create_avatar.gender_labels.male');
  if (value === 'female' || value === '女') return translate('ui.create_avatar.gender_labels.female');
  return humanizeIdentifier(raw);
}

export function formatRealmLabel(raw: string | number | null | undefined, translate: Translate): string {
  return translateByAlias(raw, REALM_ALIAS_TO_KEY, translate, 'realms');
}

export function formatStageLabel(raw: string | number | null | undefined, translate: Translate): string {
  if (typeof raw === 'number' && Number.isFinite(raw)) {
    return translate(`game.ranking.stages.${getStageKeyFromLevel(raw)}`);
  }
  return translateByAlias(raw, STAGE_ALIAS_TO_KEY, translate, 'game.ranking.stages');
}

export function formatRealmStage(
  realm: string | number | null | undefined,
  stage: string | number | null | undefined,
  translate: Translate,
): string {
  return [formatRealmLabel(realm, translate), formatStageLabel(stage, translate)].filter(Boolean).join(' ');
}

export function formatCultivationText(raw: string | number | null | undefined, translate: Translate): string {
  if (raw === null || raw === undefined) return '';
  if (typeof raw === 'number' && Number.isFinite(raw)) {
    return formatStageLabel(raw, translate);
  }

  const text = String(raw).trim();
  if (!text) return '';

  const concatenated = text.match(
    /^(qi_refinement|foundation_establishment|core_formation|nascent_soul)_?(early_stage|middle_stage|late_stage)$/i,
  );
  if (concatenated) {
    return formatRealmStage(concatenated[1], concatenated[2], translate);
  }

  const parts = text.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    const stageText = formatStageLabel(parts[parts.length - 1], translate);
    const realmText = formatRealmLabel(parts.slice(0, -1).join(' '), translate);
    if (stageText && realmText) {
      return `${realmText} ${stageText}`;
    }
  }

  const realm = REALM_ALIAS_TO_KEY[text] ?? REALM_ALIAS_TO_KEY[text.toUpperCase()] ?? REALM_ALIAS_TO_KEY[text.toLowerCase()];
  if (realm) return translate(`realms.${realm}`);
  const stage = STAGE_ALIAS_TO_KEY[text] ?? STAGE_ALIAS_TO_KEY[text.toUpperCase()] ?? STAGE_ALIAS_TO_KEY[text.toLowerCase()];
  if (stage) return translate(`game.ranking.stages.${stage}`);
  return humanizeIdentifier(text);
}

export function formatEntityGrade(raw: string | number | null | undefined, translate: Translate): string {
  if (raw === null || raw === undefined) return '';
  const trimmed = String(raw).trim();
  if (!trimmed) return '';
  if (TECHNIQUE_GRADE_KEYS.has(trimmed)) {
    return translate(`technique_grades.${trimmed}`);
  }
  return formatRealmLabel(trimmed, translate) || trimmed;
}

export function formatAttributeLabel(raw: string | number | null | undefined, translate: Translate): string {
  if (raw === null || raw === undefined) return '';
  const trimmed = String(raw).trim();
  if (!trimmed) return '';
  const normalized = trimmed.toUpperCase();
  return ATTRIBUTE_KEYS.has(normalized) ? translate(`attributes.${normalized}`) : trimmed;
}
