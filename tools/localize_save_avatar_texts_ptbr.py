from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


CJK_RE = re.compile(r"[\u3400-\u9fff]")


TRANSLATIONS: dict[str, dict[str, str]] = {
    "Qi Hanzhou": {
        "backstory": "Nascido numa família de músicos ligada ao magistrado do Vale dos Ecos, Qi Hanzhou aprendeu cedo as leis, a cítara e a arte da manipulação cortês. Aos trinta anos, desmascarou os rivais de seu clã por meio de uma melodia mortal e conquistou sua iniciação na Seita do Som que Arrebata Almas.",
        "short_term_objective": "Avançar no reino da Alma Nascente e, em seguida, reconstruir sua base de cultivo enquanto consolida sua influência por meio dos deveres da seita.",
        "long_term_objective.content": "Alcançar o Estágio Intermediário da Alma Nascente e assumir, pouco a pouco, o verdadeiro comando da Seita do Som que Arrebata Almas.",
        "thinking": "A Alma Nascente separa um ancião útil de uma autoridade que os demais precisam respeitar. A sombra de Bai Ziyan ainda cobre o Vale dos Ecos; aproveitarei esta oportunidade com cultivo disciplinado e então fortalecerei minha posição dentro da seita.",
    },
    "Dugu Jilang": {
        "backstory": "Nascido no clã Dugu, sob o Penhasco do Mar Silencioso, Jilang afastou-se da mãe e do irmão ao escolher o estudo das ervas em vez das disputas familiares. Yuan Yufei percebeu sua raiz espiritual de Vento e seu talento com agulhas ocultas, guiando-o até o Refinamento de Qi.",
        "nickname.value": "Viajante do Leque Carmesim que Escuta as Marés",
        "thinking": "O fogo fundido entra em conflito com minhas raízes de Vento e Água, mas também tempera meu caráter e pode alimentar o caminho até a Formação do Núcleo. Primeiro acumularei Cobre de Essência Rubra e, com a alquimia, produzirei elixires úteis aos poucos. O Pavilhão que Escuta as Marés não suporta aventuras impensadas, e eu não posso permanecer na Fundação.",
        "short_term_objective": "Continuar minerando Cobre de Essência Rubra e refinar elixires de Fundação em etapas, ampliando sua experiência alquímica e reunindo recursos para alcançar a Formação do Núcleo.",
        "long_term_objective.content": "Formar o Núcleo Dourado e usar a alquimia para proteger e fortalecer o Pavilhão que Escuta as Marés.",
    },
    "Yuan Yufei": {
        "backstory": "Filha de vigias mortais das marés sob o Penhasco do Mar Silencioso, Yuan Yufei foi rejeitada pela aparência severa, mas tornou-se conhecida por seu julgamento sereno. Depois de congelar a onda venenosa de um invasor yao, foi aceita no Pavilhão que Escuta as Marés e iniciou o Refinamento de Qi.",
        "nickname.value": "Imortal do Espelho Gélido do Mar Sereno",
        "nickname.reason": "Guardião do espelho no Penhasco do Mar Sereno, tem gelo e água como alicerce. Reflete a força dos inimigos através do vazio e usa as marés para contra-atacar, razão pela qual recebeu esse título.",
        "thinking": "As antigas feridas da veia espiritual do Penhasco do Mar Sereno ainda não estão claras; não devo investigá-las novamente com pressa. Primeiro curarei meus meridianos com a energia das marés da seita e estabilizarei a Formação do Núcleo. Quando cultivo e estado de espírito estiverem firmes, poderei enfrentar com calma o que se move nas sombras.",
        "short_term_objective": "Recuperar-se no Penhasco do Mar Sereno de Nanling, continuar cultivando por respiração de qi e cumprir os deveres da seita, fortalecendo o início da Formação do Núcleo e o Pavilhão que Escuta as Marés.",
        "long_term_objective.content": "Alcançar o Estágio Intermediário da Formação do Núcleo, proteger o Penhasco do Mar Sereno, orientar Dugu Jilang e fortalecer o Pavilhão que Escuta as Marés.",
    },
    "Dugu Zhan": {
        "backstory": "Filho desajeitado de um escrivão da Cidade Lanyue, Dugu Zhan serviu como magistrado do condado e evitou as disputas familiares. Ao encontrar um manual de Água e uma bolsa de Gu entre os objetos confiscados de um caso, abandonou o cargo e iniciou sozinho o Refinamento de Qi.",
        "nickname.value": "Viajante da Cítara Gélida do Mar do Norte",
        "nickname.reason": "Cultiva as Águas Místicas do Mar do Norte, vive na planície congelada e viaja sozinho com sua cítara; por isso, os cultivadores passaram a chamá-lo assim.",
        "thinking": "Embora a energia espiritual da planície congelada seja escassa, ela combina com minha raiz de Água. Posso evitar disputas de seita e obrigações sociais. Cultivar sozinho e acumular força com segurança é o caminho correto até o Estabelecimento da Fundação.",
        "short_term_objective": "Permanecer na Planície Glacial do Norte, continuar respirando qi e acumular cultivo com segurança.",
        "long_term_objective.content": "Acumular cultivo de Água gélida na Planície Glacial do Norte e alcançar o Estabelecimento da Fundação com segurança.",
    },
    "Ying Wuxiang": {
        "backstory": "Caçador de traços delicados vindo do Pântano Sombrio, Ying Wuxiang guiava assassinos pelo miasma em troca de dinheiro. Depois de emboscar um cultivador ferido com uma lança roubada, chamou a atenção do Salão do Demônio das Sombras, que lhe ensinou o Refinamento de Qi.",
        "nickname.value": "Sombra da Lança na Ponte Partida",
        "nickname.reason": "Sob uma ponte partida do pântano, uma lanterna azul revelou a sombra de um lanceiro fantasma. Ying Wuxiang atravessou a névoa sem produzir som e recebeu esse nome.",
        "fate_revelation.trigger_text": "A névoa do Pântano Sombrio se agitava ao anoitecer. Quando Ying Wuxiang pisou numa ponte de pedra meio submersa, uma lanterna azul sem pavio surgiu sob a passagem e projetou atrás dele a sombra de um lanceiro inexistente.",
        "fate_revelation.oracle_text": "Onde a lanterna afunda e a ponte se parte, a sombra da lança atravessa sem som.",
        "thinking": "O fogo venenoso do pântano quase destruiu minha base, mas isso confirma que a oportunidade da Sombra da Lança na Ponte Partida está nesta região perigosa. Primeiro controlarei os ferimentos e seguirei os sinais do pântano. Quando obtiver a lança, o Salão do Demônio das Sombras saberá quem merece ser seu batedor mais temido.",
        "short_term_objective": "Recuperar-se do veneno e explorar uma possível rota pelo Pântano Sombrio até a ponte meio submersa e a lanterna azul, evitando o sapo yao no Estabelecimento da Fundação.",
        "long_term_objective.content": "Seguir a oportunidade da Sombra da Lança na Ponte Partida, estabelecer a Fundação, conquistar a lança e tornar-se um batedor temido do Salão do Demônio das Sombras.",
    },
    "Xiao Jiaoyue": {
        "backstory": "Nascida numa família decadente de ferreiros da Cidade Qingyun, Xiao Jiaoyue fugiu de um casamento arranjado para as areias do oeste. Depois de salvar crianças de uma caravana atacada por demônios-cadáveres, encontrou entre as cinzas a Verdadeira Arte do Yang Puro e iniciou sozinha o Refinamento de Qi.",
        "nickname.value": "Fada do Bambu Trovejante das Areias Errantes",
        "nickname.reason": "Cultiva sozinha nas Areias Errantes do Oeste e usa a Espada de Bambu do Trovão Celestial para destruir espíritos malignos. Sua beleza marcante e seu comportamento reservado lhe renderam esse nome.",
        "thinking": "A energia espiritual das Areias Errantes do Oeste é escassa, mas ninguém me perturba aqui. Primeiro curarei os ferimentos antigos; depois cultivarei lentamente com a Verdadeira Arte do Yang Puro e nutrirei a espada voadora de bambu trovejante. Quando cultivo e intenção da espada estiverem firmes, poderei buscar a Alma Nascente.",
        "short_term_objective": "Permanecer nas Areias Errantes do Oeste, curar os ferimentos antigos, continuar respirando qi e nutrir a Espada de Bambu do Trovão Celestial para reforçar sua defesa.",
        "long_term_objective.content": "Cultivar em isolamento nas Areias Errantes do Oeste, acumular recursos e alcançar o reino da Alma Nascente.",
    },
    "Ximen Ruoshui": {
        "backstory": "Nascida numa cautelosa família de cartógrafos das marés da Cidade Lanyue, Ximen Ruoshui descobriu sua raiz espiritual de Água ao salvar uma bela jovem de um afogamento. Fiel à promessa feita naquele dia, seguiu eremitas do mar, aprendeu a respiração das águas místicas e tornou-se uma cultivadora independente.",
        "fate_revelation.trigger_text": "A noite ainda cobria as Marés Distantes do Mar Oriental quando Ximen Ruoshui cultivava sobre uma crista de recifes, conduzindo Água Negra pela palma no ritmo das ondas. Uma tartaruga-marinha de casco semelhante a jade surgiu da névoa e soprou para a lua uma sequência de gotas silenciosas.",
        "fate_revelation.oracle_text": "A lua afunda no casco da tartaruga; o fogo antigo ilumina o portal das marés.",
        "fate_revelation.location": "Marés Distantes do Mar Oriental",
        "thinking": "A visão da lua sobre o casco e do fogo antigo iluminando o portal das marés não surgiu por acaso. O caminho até a Alma Nascente exige prudência. Primeiro investigarei os sinais do portal nas Marés Distantes do Mar Oriental; se houver perigo, recuarei em vez de arriscar minha vida e minha base.",
        "short_term_objective": "Viajar às Marés Distantes do Mar Oriental, investigar com cautela o portal das marés e oportunidades em moradas cavernosas de Água, cultivando apenas em locais seguros.",
        "long_term_objective.content": "Seguir a oportunidade do portal das marés, encontrar uma morada cavernosa de Água, reunir recursos e alcançar a Alma Nascente com segurança.",
    },
    "Zhao Huixin": {
        "backstory": "Filha de um fabricante de cítaras da Cidade da Fronteira Sul, Zhao Huixin era ridicularizada pela aparência rústica, mas admirada por ouvir ritmos no vento. Depois que bandidos mataram sua família, seguiu os rastros deles até os campos e despertou o qi por meio da respiração das tempestades.",
        "fate_revelation.trigger_text": "A chuva acabara na Cordilheira Oriental quando Zhao Huixin atravessou uma ponte de nuvens junto a um penhasco. O vento desenhou cordas de cítara no musgo da rocha; quando ela tocou a pedra com os dedos, um antigo sino oculto na névoa ressoou três vezes.",
        "fate_revelation.oracle_text": "O vento cruza a ponte partida; o sino antigo se cala diante da lua.",
        "fate_revelation.location": "Cordilheira Oriental",
        "thinking": "Conquistei o Santuário de Metal de Taibai, mas ele não é uma terra espiritual de Vento. Primeiro retornarei aos Campos Centrais para reunir crinas de cavalos velozes e observar sinais de cultivadores malignos. Com recursos suficientes, seguirei para oeste em busca de uma veia de Vento capaz de estabilizar minha Alma Nascente.",
        "short_term_objective": "Viajar aos Campos Centrais para caçar Cavalos do Vento e obter suas crinas, explorando o oeste em busca de terras espirituais de Vento e ameaças ocultas.",
        "long_term_objective.content": "Proteger o Santuário de Metal de Taibai, encontrar o antigo sino da Cordilheira Oriental e eliminar as ameaças malignas dos Campos Centrais.",
    },
    "Bai Ziyan": {
        "backstory": "Filha de um artesão de instrumentos pouco estimado do Vale dos Ecos, Bai Ziyan era tratada como portadora de mau agouro, mas conseguia ouvir intenções assassinas nas melodias. Depois de revelar a traição de um cultivador errante, tomou seu método da raiz de Metal e iniciou sozinha o Refinamento de Qi.",
        "current_action.state.task_title": "Guardar a entrada da área proibida",
        "thinking": "A formação protetora do Vale dos Ecos está pronta, mas o Pavilhão das Escrituras ainda precisa de uma guarda segura. Qi Hanzhou está próximo, porém continua sendo apenas um estranho e não merece minha atenção. Primeiro fortalecerei a base do Estágio Avançado da Alma Nascente com a energia da seita; depois tratarei do Reino Místico das Águas Profundas e das ameaças internas.",
        "short_term_objective": "Cumprir a missão de guardar o Pavilhão das Escrituras, permanecer no Vale dos Ecos para cultivar e nutrir o Leque Yin-Yang, fortalecendo as defesas da seita e sua base no Estágio Avançado da Alma Nascente.",
        "long_term_objective.content": "Fortalecer a Seita do Som que Arrebata Almas e o Reino Místico das Águas Profundas, eliminar ameaças internas e alcançar o ápice da Alma Nascente.",
    },
    "Sima Lei": {
        "backstory": "Nascido numa família pobre de escribas da Cidade Qingyun, Sima Lei sobreviveu a uma seca ao perceber o qi de Água oculto no subsolo. Um daoísta errante lhe ensinou a Palma do Relâmpago e então desapareceu, deixando-o cultivar sozinho.",
        "nickname.value": "Trovão Oculto das Areias Errantes",
        "nickname.reason": "Nas profundezas das areias, ele percebe veios de Água e mantém sua força oculta. Parece frágil em tempos comuns, mas sua Palma do Relâmpago afugenta qualquer agressor.",
        "thinking": "Preciso agir com segurança. Os espinhos de cacto das Areias Errantes do Oeste servem aos meus planos; primeiro reunirei materiais e depois praticarei alquimia com cuidado. Mesmo que a tentativa anterior tenha virado cinzas, não permitirei que um fracasso me afaste do caminho correto nem da meta de estabelecer a Fundação.",
        "short_term_objective": "Continuar coletando espinhos de cacto, reunir material suficiente para tentar refinar elixires de Refinamento de Qi e estabilizar o cultivo por meio da respiração de qi.",
        "long_term_objective.content": "Acumular recursos com a alquimia, manter seus talentos ocultos, seguir o caminho correto e avançar com firmeza até o Estabelecimento da Fundação.",
    },
    "Qi Lin": {
        "backstory": "Nascida numa família de caçadores da Cidade da Fronteira Sul, Qi Lin aprendeu a usar lâminas e armas ocultas enquanto protegia caravanas nas montanhas. Depois de tomar o manual de Gelo Profundo de um cultivador independente morto, forçou sozinha o despertar de sua percepção de qi da raiz de Terra.",
        "fate_revelation.trigger_text": "O vento do entardecer atravessava os canais das Planícies do Sudeste quando Qi Lin passou por uma ponte de pedra meio coberta de juncos. Sob a ponte surgiram pegadas azuis de cervo; ao tocar suas armas ocultas, ela viu na água o reflexo de uma lua crescente que se movia ao contrário.",
        "fate_revelation.oracle_text": "A lua crescente afunda sob a ponte; as pegadas do cervo abrem o caminho para as montanhas.",
        "fate_revelation.location": "Planícies do Sudeste",
        "thinking": "Ainda estou longe do Estabelecimento da Fundação. As Cem Mil Montanhas são perigosas, mas oferecem mais oportunidades que desperdiçar tempo no mar. Primeiro explorarei a periferia e procurarei discretamente pistas sobre armas ocultas adequadas. Se encontrar uma fera yao de nível elevado, recuarei em vez de travar uma luta inútil.",
        "short_term_objective": "Chegar à periferia das Cem Mil Montanhas, explorar com cautela áreas desconhecidas e procurar oportunidades de baixo risco e pistas sobre armas ocultas.",
        "long_term_objective.content": "Buscar oportunidades nas montanhas, alcançar o Estabelecimento da Fundação e obter armas ocultas adequadas.",
    },
}


def _set_path(target: dict, path: str, value: str) -> None:
    parts = path.split(".")
    current = target
    for part in parts[:-1]:
        child = current.get(part)
        if not isinstance(child, dict):
            raise ValueError(f"Campo ausente ou incompatível: {path}")
        current = child
    if parts[-1] not in current:
        raise ValueError(f"Campo ausente: {path}")
    current[parts[-1]] = value


def localize_save(data: dict) -> dict:
    avatars = data.get("avatars")
    if not isinstance(avatars, list):
        raise ValueError("O save não contém uma lista de avatares")

    by_name = {str(avatar.get("name", "")): avatar for avatar in avatars if isinstance(avatar, dict)}
    missing = sorted(set(TRANSLATIONS) - set(by_name))
    if missing:
        raise ValueError(f"Avatares esperados não encontrados: {', '.join(missing)}")

    for name, replacements in TRANSLATIONS.items():
        avatar = by_name[name]
        for path, value in replacements.items():
            _set_path(avatar, path, value)

    remaining: list[str] = []
    for name, avatar in by_name.items():
        for field in ("backstory", "thinking", "short_term_objective"):
            value = avatar.get(field)
            if isinstance(value, str) and CJK_RE.search(value):
                remaining.append(f"{name}.{field}")
        objective = avatar.get("long_term_objective")
        if isinstance(objective, dict):
            value = objective.get("content")
            if isinstance(value, str) and CJK_RE.search(value):
                remaining.append(f"{name}.long_term_objective.content")
    if remaining:
        raise ValueError(f"Textos narrativos ainda contêm CJK: {', '.join(remaining)}")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Localiza os textos narrativos dos avatares do save atual para pt-BR.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        raise SystemExit("A saída deve ser um novo arquivo; edição in-place não é permitida.")
    if args.output.exists():
        raise SystemExit(f"A saída já existe: {args.output}")

    with args.input.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    localized = localize_save(data)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(localized, handle, ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
