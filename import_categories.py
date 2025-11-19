#!/usr/bin/env python3
"""
Script to import categories and subcategories data into Google Sheets.
Creates the categories_subcategories worksheet and imports the provided data.
"""

import os
import sys
from config import conf
from services.sheets_api import sheets_api

def import_categories_data():
    """Import categories and subcategories data into Google Sheets."""

    # The data provided by the user (tab-separated format)
    categories_data = """Category	Node_id_category	Subcategory	Node_id_subcategory
Apparel	2892859031	Abbigliamento da notte, lingerie e intimo	21695399031
Apparel	2892859031	Abbigliamento premaman	1806562031
Apparel	2892859031	Abbigliamento sportivo	1347370031
Apparel	2892859031	Body	15664266031
Apparel	2892859031	Calze e collant	2892907031
Apparel	2892859031	Felpe	14704080031
Apparel	2892859031	Giacche e cappotti	2892908031
Apparel	2892859031	Gonne	2892911031
Apparel	2892859031	Jeans	2892912031
Apparel	2892859031	Leggings	2892913031
Apparel	2892859031	Maglioni e cardigan	2892915031
Apparel	2892859031	Mare e piscina	3950200031
Apparel	2892859031	Monopezzi e tutine	2892917031
Apparel	2892859031	Neve e pioggia	2892918031
Apparel	2892859031	Pantaloncini	2892919031
Apparel	2892859031	Pantaloni	2892920031
Apparel	2892859031	Salopette	2892922031
Apparel	2892859031	T-shirt, top e bluse	2892923031
Apparel	2892859031	Tailleur e giacche	2892924031
Apparel	2892859031	Vestiti	2892904031
Automotive	1571281031	Accessori e parti per camper	2420754031
Automotive	1571281031	Accessori e parti per veicolo agricolo	15621221031
Automotive	1571281031	Accessori per auto	2420687031
Automotive	1571281031	Accessori per viaggio e trasporto	2420814031
Automotive	1571281031	Articoli regalo e merchandising	2420919031
Automotive	1571281031	Attrezzi per veicoli	2420850031
Automotive	1571281031	Cerchioni e pneumatici	2420860031
Automotive	1571281031	Cura auto e moto	2420872031
Automotive	1571281031	Elettronica per veicoli	3013890031
Automotive	1571281031	Moto, accessori e componenti	2420930031
Automotive	1571281031	Navigatori Satellitari	2901657031
Automotive	1571281031	Oli e liquidi	2421122031
Automotive	1571281031	Parti per auto	2421149031
Automotive	1571281031	Verniciatura	2421388031
Baby	1571287031	Abbigliamento e scarpine	5518833031
Baby	1571287031	Allattamento e pappa	1739201031
Baby	1571287031	Attività e intrattenimento	1806378031
Baby	1571287031	Cambio del pannolino	1806548031
Baby	1571287031	Cameretta	1739196031
Baby	1571287031	Educazione al vasino e pedane	1806725031
Baby	1571287031	Giochi prima infanzia	632582031
Baby	1571287031	Igiene e benessere	1739204031
Baby	1571287031	Marsupi e accessori	1806413031
Baby	1571287031	Maternità	21095378031
Baby	1571287031	Passeggini rimorchio per bici e accessori	1806763031
Baby	1571287031	Passeggini, carrozzine e accessori	1739200031
Baby	1571287031	Regali per neonati	3735570031
Baby	1571287031	Seggiolini auto e accessori	1739199031
Baby	1571287031	Sicurezza	1739197031
Baby	1571287031	Succhietti e massaggiagengive	1806720031
Beauty	6198083031	Accessori e strumenti di bellezza	6306896031
Beauty	6198083031	Attrezzature per saloni e spa	27088076031
Beauty	6198083031	Bagno e corpo	4327880031
Beauty	6198083031	Cura dei capelli	4327902031
Beauty	6198083031	Cura della pelle	6306897031
Beauty	6198083031	Fragranze e profumi	6306898031
Beauty	6198083031	Manicure e pedicure	6306899031
Beauty	6198083031	Trucco	6306900031
Books	411664031	Adolescenti e ragazzi	13077484031
Books	411664031	Arte, cinema e fotografia	508758031
Books	411664031	Biografie, diari e memorie	508714031
Books	411664031	Calendari e agende	508791031
Books	411664031	Diritto	508785031
Books	411664031	Dizionari e opere di consultazione	508864031
Books	411664031	Economia, affari e finanza	508786031
Books	411664031	Erotica	13466594031
Books	411664031	Famiglia, salute e benessere	508792031
Books	411664031	Fantascienza e Fantasy	1345828031
Books	411664031	Fumetti e manga	508784031
Books	411664031	Gialli e Thriller	508771031
Books	411664031	Guide di revisione e aiuto allo studio	1346712031
Books	411664031	Humour	508820031
Books	411664031	Informatica, Web e Digital Media	508733031
Books	411664031	Letteratura e narrativa	508770031
Books	411664031	Libri LGBTQ+	95162791031
Books	411664031	Libri per bambini	508715031
Books	411664031	Libri scolastici	508888031
Books	411664031	Libri universitari	15216198031
Books	411664031	Lingua, linguistica e scrittura	508857031
Books	411664031	Politica	508811031
Books	411664031	Religione	508745031
Books	411664031	Romanzi rosa	508775031
Books	411664031	Scienze, tecnologia e medicina	508867031
Books	411664031	Self-help	508794031
Books	411664031	Società e scienze sociali	508879031
Books	411664031	Sport	508835031
Books	411664031	Storia	508796031
Books	411664031	Tempo libero	508821031
Books	411664031	Viaggi	508753031
Computers	425917031	Accessori	460002031
Computers	425917031	Barebone	460081031
Computers	425917031	Componenti e pezzi di ricambio	460080031
Computers	425917031	Desktop	460127031
Computers	425917031	Dispositivi archiviazione dati	17492752031
Computers	425917031	Monitor	460159031
Computers	425917031	Periferiche di rete	460161031
Computers	425917031	Portatili	460158031
Computers	425917031	Scanner e accessori	17492750031
Computers	425917031	Server	460187031
Computers	425917031	Stampanti e accessori	17492751031
Computers	425917031	Tablet PC	460188031
Computers	425917031	Tavolette per scrittura LCD ed eWriters	15424896031
DigitalMusic	1748204031	Blues	1786699031
DigitalMusic	1748204031	Colonne sonore	1786720031
DigitalMusic	1748204031	Country	1786704031
DigitalMusic	1748204031	Dance ed Elettronica	1786705031
DigitalMusic	1748204031	Easy Listening	1786706031
DigitalMusic	1748204031	Folk	1786707031
DigitalMusic	1748204031	Hard Rock e Metal	1786708031
DigitalMusic	1748204031	Hip-Hop e Rap	1786709031
DigitalMusic	1748204031	Indie e Alternativa	1786710031
DigitalMusic	1748204031	Jazz	1786711031
DigitalMusic	1748204031	Miscellanea	1786713031
DigitalMusic	1748204031	Musica classica	1786703031
DigitalMusic	1748204031	Musica internazionale	1786721031
DigitalMusic	1748204031	Musica latina	1786712031
DigitalMusic	1748204031	Musica per bambini	1786700031
DigitalMusic	1748204031	Musica religiosa e Gospel	1786701031
DigitalMusic	1748204031	Musical e Cabaret	1786714031
DigitalMusic	1748204031	New Age	1786715031
DigitalMusic	1748204031	Pop	1786716031
DigitalMusic	1748204031	R&B e Soul	1786717031
DigitalMusic	1748204031	Reggae	1786718031
DigitalMusic	1748204031	Rock	1786719031
DigitalMusic	1748204031	Rock classico	1786702031
Electronics	412610031	Accessori di alimentazione elettrica	17532506031
Electronics	412610031	Audio e video portatile	473287031
Electronics	412610031	Cellulari e accessori	1497228031
Electronics	412610031	Cuffie, auricolari e accessori	15512873031
Electronics	412610031	eBook Reader e accessori	1462698031
Electronics	412610031	Elettronica per veicoli	1465649031
Electronics	412610031	Foto e videocamere	435505031
Electronics	412610031	Garanzie	473584031
Electronics	412610031	GPS, Trova oggetti e accessori	435508031
Electronics	412610031	Home Audio e Hi-Fi	473357031
Electronics	412610031	Home Cinema, TV e video	435504031
Electronics	412610031	Informatica	473601031
Electronics	412610031	Pile e caricabatterie	473568031
Electronics	412610031	Radiocomunicazione	1463267031
Electronics	412610031	Sigarette e narghilè elettronici e accessori	4327086031
Electronics	412610031	Tablet	460188031
Electronics	412610031	Tecnologia indossabile	49981441031
Electronics	412610031	Telefonia fissa e accessori	1497227031
Fashion	5512286031	Arborist Merchandising Root	89757735031
Fashion	5512286031	Categorie	5512287031
Fashion	5512286031	Featured Categories	5512288031
Fashion	5512286031	Specialty Stores	5512289031
GardenAndOutdoor	635017031	Arredamento da giardino e accessori	731468031
GardenAndOutdoor	635017031	Attrezzi da giardino e attrezzature per l'irrigazione	26389479031
GardenAndOutdoor	635017031	Barbecue e picnic	731471031
GardenAndOutdoor	635017031	Decorazioni per il giardino	731467031
GardenAndOutdoor	635017031	Giardinaggio	731469031
GardenAndOutdoor	635017031	Organizzazione degli spazi esterni e contenitori	731466031
GardenAndOutdoor	635017031	Piante, semi e bulbi	4369065031
GardenAndOutdoor	635017031	Piscine, vasche idromassaggio e accessori	4438733031
GardenAndOutdoor	635017031	Rimozione della neve	3119722031
GardenAndOutdoor	635017031	Riscaldamenti e bracieri da esterno	4348612031
GardenAndOutdoor	635017031	Tagliaerba e utensili elettrici da giardino	731505031
GardenAndOutdoor	635017031	Temperature e dispositivi metereologici	9337408031
GardenAndOutdoor	635017031	Uccelli e piccoli animali del giardino	4380634031
GiftCards	3557018031	Buoni regalo	4262301031
GroceryAndGourmetFood	6198093031	Alimenti freschi e refrigerati	21902039031
GroceryAndGourmetFood	6198093031	Birra, vino e alcolici	6377736031
GroceryAndGourmetFood	6198093031	Caffè, tè e bevande	6377842031
GroceryAndGourmetFood	6198093031	Carne	6377950031
GroceryAndGourmetFood	6198093031	Cereali da colazione	88363333031
GroceryAndGourmetFood	6198093031	Cesti e confezioni regalo	6378086031
GroceryAndGourmetFood	6198093031	Cibi in scatola e conserve	6378100031
GroceryAndGourmetFood	6198093031	Erbe aromatiche e spezie	6378317031
GroceryAndGourmetFood	6198093031	Frutta e verdura	6387848031
GroceryAndGourmetFood	6198093031	Latticini, uova e alternative vegetali	6394133031
GroceryAndGourmetFood	6198093031	Marmellate, miele e creme spalmabili	6392956031
GroceryAndGourmetFood	6198093031	Oli, aceti e condimenti per insalata	6392971031
GroceryAndGourmetFood	6198093031	Pasta, riso e legumi secchi	6392912031
GroceryAndGourmetFood	6198093031	Pasticceria e prodotti da forno	6394639031
GroceryAndGourmetFood	6198093031	Pesce e frutti di mare	20934044031
GroceryAndGourmetFood	6198093031	Preparati da cucina e da forno	6393113031
GroceryAndGourmetFood	6198093031	Salse e sughi	6394812031
GroceryAndGourmetFood	6198093031	Snack dolci e salati	6394874031
GroceryAndGourmetFood	6198093031	Surgelati	6377517031
GroceryAndGourmetFood	6198093031	Svezzamento e pappine	1806695031
HealthPersonalCare	1571290031	Alimentazione e nutrizione	4327117031
HealthPersonalCare	1571290031	Articoli per fumatori	6308772031
HealthPersonalCare	1571290031	Ausili per la mobilità e vita quotidiana	4327135031
HealthPersonalCare	1571290031	Benessere	4327083031
HealthPersonalCare	1571290031	Cura della vista	4327084031
HealthPersonalCare	1571290031	Cura di bambini e neonati	4327085031
HealthPersonalCare	1571290031	Erotismo e contraccezione	4327082031
HealthPersonalCare	1571290031	Igiene dentale	4327087031
HealthPersonalCare	1571290031	Igiene intima	6691169031
HealthPersonalCare	1571290031	Prodotti e apparecchiature mediche	4327089031
HealthPersonalCare	1571290031	Prodotti per la medicazione	4327088031
HealthPersonalCare	1571290031	Pulizia e cura della casa	6394759031
HealthPersonalCare	1571290031	Rasatura, epilazione e rimozione peli	4327090031
HealthPersonalCare	1571290031	Vitamine, minerali e integratori	4327246031
HomeAndKitchen	524016031	Arredamento	2808571031
HomeAndKitchen	524016031	Aspirapolvere e pulizia di pavimenti e finestre	732998031
HomeAndKitchen	524016031	Bagno	3225815031
HomeAndKitchen	524016031	Climatizzazione e riscaldamento	3692884031
HomeAndKitchen	524016031	Contenitori e barattoli	652509031
HomeAndKitchen	524016031	Decorazioni per interni	731676031
HomeAndKitchen	524016031	Detergenti e prodotti per la pulizia	733029031
HomeAndKitchen	524016031	Distributori d'acqua, caraffe filtranti e cartucce	652719031
HomeAndKitchen	524016031	Elettrodomestici per la casa	679995031
HomeAndKitchen	524016031	Elettrodomestici per la cucina	602473031
HomeAndKitchen	524016031	Ferri da stiro e accessori	732997031
HomeAndKitchen	524016031	Garanzie	13713023031
HomeAndKitchen	524016031	Hobby creativi	4340026031
HomeAndKitchen	524016031	Illuminazione per interni	1849538031
HomeAndKitchen	524016031	Organizzazione interni	731678031
HomeAndKitchen	524016031	Pentole, padelle e pirofile	2962254031
HomeAndKitchen	524016031	Produzione di birra e vino artigianali	3683687031
HomeAndKitchen	524016031	Tè e caffè	602474031
HomeAndKitchen	524016031	Teglie da forno e accessori per pasticceria	652471031
HomeAndKitchen	524016031	Tessili per la casa	731677031
HomeAndKitchen	524016031	Utensili da cucina	652535031
HomeAndKitchen	524016031	Vasellame	652615031
Industrial	5866069031	Attrezzatura  e allestimento per negozi	6311641031
Industrial	5866069031	Attrezzature e forniture agricole	15800210031
Industrial	5866069031	Attrezzature e forniture per servizi di ristorazione	10417753031
Industrial	5866069031	Energia solare e eolica	14897362031
Industrial	5866069031	Forniture mediche professionali	6571983031
Industrial	5866069031	Forniture per imballaggio e spedizione	6311637031
Industrial	5866069031	Forniture per l'istruzione	16243687031
Industrial	5866069031	Forniture sanitarie e igieniche	6571987031
Industrial	5866069031	Idraulica, pneumatici e tubatura	6311633031
Industrial	5866069031	Impianti elettrici	6311634031
Industrial	5866069031	Materie prime	6311640031
Industrial	5866069031	Prodotti abrasivi e per finitura	6311628031
Industrial	5866069031	Prodotti di filtrazione	6311632031
Industrial	5866069031	Prodotti odontoiatrici	6311639031
Industrial	5866069031	Prodotti per il trasporto materiali	6311636031
Industrial	5866069031	Prodotti per la trasmissione di energia	6311638031
Industrial	5866069031	Prodotti salute e sicurezza sul lavoro	6571993031
Industrial	5866069031	Prodotti scientifici e per laboratorio	6571995031
Industrial	5866069031	Stampa e scansione 3D	6571991031
Industrial	5866069031	Strumenti da taglio	6311630031
Industrial	5866069031	Test e misurazione	6571998031
Industrial	5866069031	Utensili manuali e elettrici	6571998031
KindleStore	1331141031	eBook Kindle	827182031
KindleStore	1331141031	Prime Reading	14808852031
Lighting	1571293031	Illuminazione bagno	3837349031
Lighting	1571293031	Illuminazione per esterni	1849540031
Lighting	1571293031	Illuminazione per interni	1849538031
Lighting	1571293031	Lampadine	1849539031
Lighting	1571293031	Luci natalizie	3837356031
Lighting	1571293031	Strisce LED	1904562031
MobileApps	1661661031	Comunicazione	1725425031
MobileApps	1661661031	Consultazione	1725447031
MobileApps	1661661031	Cucina	1725426031
MobileApps	1661661031	Curiosità	1725442031
MobileApps	1661661031	Economia e finanza	1725423031
MobileApps	1661661031	Fotografia	1725443031
MobileApps	1661661031	Giochi	1725429031
MobileApps	1661661031	Giornali e notiziari	1725441031
MobileApps	1661661031	Immobili	1725446031
MobileApps	1661661031	Informazioni utili sulle città	1725424031
MobileApps	1661661031	Intrattenimento	1725428031
MobileApps	1661661031	Istruzione	1725427031
MobileApps	1661661031	Libri e fumetti	1725417031
MobileApps	1661661031	Lifestyle	1725432031
MobileApps	1661661031	Meteorologia	1725464031
MobileApps	1661661031	Motivi	1725452031
MobileApps	1661661031	Musica	1725434031
MobileApps	1661661031	Navigazione	1725440031
MobileApps	1661661031	Podcast	1725444031
MobileApps	1661661031	Produttività	1725445031
MobileApps	1661661031	Ragazzi	1725431031
MobileApps	1661661031	Riviste	1725433031
MobileApps	1661661031	Salute e benessere	1725430031
MobileApps	1661661031	Shopping	1725449031
MobileApps	1661661031	Social Network	1725450031
MobileApps	1661661031	Sport	1725451031
MobileApps	1661661031	Suonerie	1725448031
MobileApps	1661661031	Utility	1725454031
MobileApps	1661661031	Viaggi	1725453031
MobileApps	1661661031	Web Browser	1725465031
MoviesAndTV	412607031	Film	5715226031
MoviesAndTV	412607031	Serie TV	435482031
Music	412601031	Altro	5724383031
Music	412601031	Blues	489694031
Music	412601031	Colonne sonore	489829031
Music	412601031	Country	489712031
Music	412601031	Dance ed Elettronica	489722031
Music	412601031	Facile Ascolto	489730031
Music	412601031	Folk	489733031
Music	412601031	Hard Rock e Metal	489747031
Music	412601031	Indie e Alternativa	489682031
Music	412601031	Jazz	489762031
Music	412601031	Musica Classica	435475031
Music	412601031	Musica internazionale	489835031
Music	412601031	Musica italiana	5724228031
Music	412601031	Musica per bambini, giochi e storie	489775031
Music	412601031	Musical e cabaret	5724439031
Music	412601031	New Age e meditazione	489783031
Music	412601031	Pop	489784031
Music	412601031	R&B e Soul	489795031
Music	412601031	Rap e Hip-hop	489802031
Music	412601031	Reggae	489809031
Music	412601031	Rock	489814031
Music	412601031	Video e concerti	5724416031
MusicalInstruments	3628630031	Accessori per riproduzione musicale	5021793031
MusicalInstruments	3628630031	Apparecchiature di registrazione	5021801031
MusicalInstruments	3628630031	Attrezzature per DJ e VJ	5021795031
MusicalInstruments	3628630031	Attrezzature per karaoke	5021794031
MusicalInstruments	3628630031	Bassi, chitarre ed equipaggiamento	5021796031
MusicalInstruments	3628630031	Batterie e percussioni	5021797031
MusicalInstruments	3628630031	Microfoni e accessori	5021799031
MusicalInstruments	3628630031	Pianoforti, tastiere e accessori	5021800031
MusicalInstruments	3628630031	Sintetizzatori, campionatori e strumenti digitali	5021802031
MusicalInstruments	3628630031	Sonorizzazione e palcoscenico	5021803031
MusicalInstruments	3628630031	Spartiti, canzonieri e testi	8537379031
MusicalInstruments	3628630031	Strumenti a corda	5021805031
MusicalInstruments	3628630031	Strumenti a fiato	5021804031
OfficeProducts	3606311031	Archivio ufficio e accessori per scrivania	4290080031
OfficeProducts	3606311031	Arredamento e illuminazione	4290081031
OfficeProducts	3606311031	Buste e materiali per spedizioni	4290082031
OfficeProducts	3606311031	Calendari, agende, rubriche e organizer	4290083031
OfficeProducts	3606311031	Carta, blocchi e quaderni	4290084031
OfficeProducts	3606311031	Elettronica per ufficio	3474614031
OfficeProducts	3606311031	Penne, matite, scrittura e correzione	4290086031
OfficeProducts	3606311031	Scuola e materiale didattico	4290087031
Software	412613031	Antivirus e Software di sicurezza	486461031
Software	412613031	Casa e Hobby	486516031
Software	412613031	Contabilità e finanza	14639567031
Software	412613031	Corsi di lingue e viaggi	14639573031
Software	412613031	Fotografia e disegno grafico	14639572031
Software	412613031	Gestione fiscale	486548031
Software	412613031	Istruzione e consultazione	486469031
Software	412613031	Musica	14639574031
Software	412613031	Produzione video	14639577031
Software	412613031	Programmazione e sviluppo siti internet	486560031
Software	412613031	Reti e Server	14639575031
Software	412613031	Sistemi operativi	486541031
Software	412613031	Software di base	486588031
Software	412613031	Software per bambini	486450031
Software	412613031	Ufficio	435515031
SportsAndOutdoors	524013031	Abbigliamento sportivo	937262031
SportsAndOutdoors	524013031	Accessori	937267031
SportsAndOutdoors	524013031	Accessori per sport e attività ricreative all'aperto	26039479031
SportsAndOutdoors	524013031	Attività ricreative all'aperto	26039477031
SportsAndOutdoors	524013031	Caccia e Pesca	26039476031
SportsAndOutdoors	524013031	Cofanetti regalo	4582622031
SportsAndOutdoors	524013031	Dispositivi elettronici	937268031
SportsAndOutdoors	524013031	Espositori e custodie	967387031
SportsAndOutdoors	524013031	Fan Shop	968488031
SportsAndOutdoors	524013031	Fitness e palestra	937257031
SportsAndOutdoors	524013031	Medicina dello sport	4551672031
SportsAndOutdoors	524013031	Scarpe sportive	5160113031
SportsAndOutdoors	524013031	Sport	26039478031
SportsAndOutdoors	524013031	Sport di svago	3635984031
SportsAndOutdoors	524013031	Tavoli e superfici di gioco	969483031
SportsAndOutdoors	524013031	Zaini e borse sportive	4379907031
ToolsAndHomeImprovement	2454161031	Attrezzature per cucine e bagni	3119607031
ToolsAndHomeImprovement	2454161031	Attrezzi elettrici da giardinaggio	731505031
ToolsAndHomeImprovement	2454161031	Caminetti e accessori	731690031
ToolsAndHomeImprovement	2454161031	Ferramenta	3119610031
ToolsAndHomeImprovement	2454161031	Materiale elettrico	3119611031
ToolsAndHomeImprovement	2454161031	Organizzazione casa e magazzini	3119612031
ToolsAndHomeImprovement	2454161031	Pitture, trattamenti per pareti e utensili	3119613031
ToolsAndHomeImprovement	2454161031	Prodotti per la costruzione	3119614031
ToolsAndHomeImprovement	2454161031	Sicurezza e protezione	3119615031
ToolsAndHomeImprovement	2454161031	Tubature	3119616031
ToolsAndHomeImprovement	2454161031	Utensili elettrici e a mano	3119617031
ToysAndGames	523998031	Articoli da regalo e scherzetti	632835031
ToysAndGames	523998031	Attività creative	632540031
ToysAndGames	523998031	Bambole e accessori	632667031
ToysAndGames	523998031	Burattini e teatrini	632880031
ToysAndGames	523998031	Calendari dell'avvento	5259714031
ToysAndGames	523998031	Costruzioni	632623031
ToysAndGames	523998031	Elettronica per bambini	632697031
ToysAndGames	523998031	Giocattoli da collezione	20473090031
ToysAndGames	523998031	Giocattoli prima infanzia	632582031
ToysAndGames	523998031	Giochi d'imitazione e accessori di travestimento	632869031
ToysAndGames	523998031	Giochi da tavola, di società e accessori	632730031
ToysAndGames	523998031	Giochi educativi e scientifici	601294031
ToysAndGames	523998031	Modellismo e costruzione	14515672031
ToysAndGames	523998031	Peluche	632863031
ToysAndGames	523998031	Personaggi giocattolo	20501724031
ToysAndGames	523998031	Puzzle	632888031
ToysAndGames	523998031	Radiocomandati e telecomandati	632898031
ToysAndGames	523998031	Sport e giochi all'aperto	602299031
ToysAndGames	523998031	Strumenti musicali giocattolo	632829031
ToysAndGames	523998031	Veicoli	20389819031
VideoGames	412604031	Xbox Series X e S	20904366031
VideoGames	412604031	PlayStation 5	20904349031
VideoGames	412604031	Nintendo Switch 2	206234251031
VideoGames	412604031	Nintendo Switch	12366208031
VideoGames	412604031	Xbox One	2785638031
VideoGames	412604031	PlayStation 4	2569674031
VideoGames	412604031	PC	13900025031
VideoGames	412604031	Mac	13900075031
VideoGames	412604031	Realtà virtuale	22472721031
VideoGames	412604031	Sistemi legacy	26869613031
VideoGames	412604031	Abbonamenti e carte prepagate	15891687031
VideoGames	412604031	Sistemi di gioco portatili	92555809031"""

    print("🔄 Starting categories and subcategories import...")

    # Parse the data into rows
    lines = categories_data.strip().split('\n')
    data_rows = []

    for line in lines:
        # Split by tab character
        row = line.split('\t')
        data_rows.append(row)

    print(f"📊 Parsed {len(data_rows)} rows of data")
    print(f"📋 Headers: {data_rows[0]}")
    print(f"📈 Data rows: {len(data_rows) - 1}")

    # Check if Google Sheets API is available
    if not sheets_api.available:
        print("⚠️ Google Sheets API not available. Cannot import data.")
        return False

    try:
        # Try to create the worksheet (it might already exist)
        try:
            worksheet = sheets_api.gc.create(f"categories_subcategories", rows=len(data_rows), cols=4)
            print("✅ Created new worksheet 'categories_subcategories'")
        except Exception as e:
            print(f"ℹ️ Worksheet might already exist: {e}")
            # Try to get existing worksheet
            try:
                worksheet = sheets_api.spreadsheet.worksheet("categories_subcategories")
                print("✅ Using existing worksheet 'categories_subcategories'")
            except Exception as e2:
                print(f"❌ Cannot access worksheet: {e2}")
                return False

        # Clear existing data and update with new data
        worksheet.clear()
        worksheet.update(data_rows)
        print("✅ Successfully imported categories and subcategories data!")

        # Verify the import
        verify_data = worksheet.get_all_values()
        if len(verify_data) > 1:
            print(f"✅ Verification: {len(verify_data)} rows imported successfully")
            print(f"   Sample: {verify_data[1][:2]}...")  # Show first category
        else:
            print("❌ Verification failed: No data found after import")
            return False

        return True

    except Exception as e:
        print(f"❌ Error importing data: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = import_categories_data()
    if success:
        print("\n🎉 Categories import completed successfully!")
        print("📝 You can now test the campaign creation - Step 2 should show categories.")
    else:
        print("\n❌ Categories import failed.")
        sys.exit(1)
