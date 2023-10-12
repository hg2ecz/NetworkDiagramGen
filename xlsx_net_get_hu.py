#!/usr/bin/python3

# Krüpl Zsolt, 2023. október 11.

import re
import os
import sys
import copy
import json
import xlrd
import codecs

GENDIR="generated_out"

objtype_whitelist = ["net", "router", "switch", "server", "phone"]
conn_whitelist = ["nincs", "serial", "eth", "mgmt", "vlan", "vpn", "bond"]

# Doksigen
def doksi_ossszefuzes(filename):
    os.chdir(GENDIR)
    if not os.path.exists("../"+filename):
        print ("\n\nNincs a mappában    %s    leíró állomány, nem generálódik összefűzött doksi.\n\n"%(filename))
        return
    osszefuz_fd = open("doksi-"+filename, "w")
    osszefuz_fd.write("""\\documentclass[12pt, a4paper]{article}
\\usepackage[magyar]{babel}
\\usepackage{t1enc}
\\usepackage{times}
\\usepackage[colorlinks=true, pdfstartview=FitV, linkcolor=blue, citecolor=blue, urlcolor=blue]{hyperref}
\\usepackage[a4paper, margin=2.5cm]{geometry}
\\usepackage[final]{pdfpages}
\\begin{document}
\\thispagestyle{empty}
\\tableofcontents
\\newpage
""")

    szoveg = ""
    for s in open("../"+filename, 'r'):
        if s[:2] == "[[":
            pdfnev = s[2:].rstrip()[:-2].strip()
            osszefuz_fd.write("\\includepdf[scale=0.9,pagecommand={%s}]{%s}\n\n"%(szoveg, pdfnev));
            szoveg = ""
            continue
        else:
            if len(s.strip()) != 0:
                szoveg += s
    osszefuz_fd.write("\\end{document}\n");
    osszefuz_fd.close()
    if checkonly == False:
        os.system("pdflatex \'doksi-"+filename+"\'")
        os.system("pdflatex \'doksi-"+filename+"\'")
    os.chdir("..")

# Ábragen
g_outfd = None
def place_node(name, typ, mgmtip, xpos, ypos, show):
    global g_outfd
    name_esc = name.replace('_', '\_')
    name_id = name.replace('(', '[')
    name_id = name_id.replace(')', ']')
    hidden=""
    if show == False:
        hidden="hidden"

    if typ.upper() == "ROUTER":
        g_outfd.write("  \\node[xshift=%scm, yshift=%scm] (%s) {\\router%s{%s}{%s}};\n"%(xpos, -ypos, name_id, hidden, name_esc, mgmtip))

    if typ.upper() == "SWITCH":
        g_outfd.write("  \\node[xshift=%scm, yshift=%scm] (%s) {\\switch%s{%s}{%s}};\n"%(xpos, -ypos, name_id, hidden,name_esc, mgmtip))

    if typ.upper() == "SERVER":
        g_outfd.write("  \\node[xshift=%scm, yshift=%scm] (%s) {\\server%s{%s}{%s}};\n"%(xpos, -ypos, name_id, hidden, name_esc, mgmtip))

    if typ.upper() == "PHONE":
        g_outfd.write("  \\node[xshift=%scm, yshift=%scm] (%s) {\\phone%s{%s}{%s}};\n"%(xpos, -ypos, name_id, hidden, name_esc, mgmtip))

    if typ.upper() == "NET":
        if show == True:
            g_outfd.write("  \\node[cloud, draw=blue, text=cyan, fill=gray!10, minimum width=9cm, minimum height=6cm, xshift=%scm, yshift=%scm] (%s) at (0,0) {\\Huge %s};\n"%(xpos, -ypos, name_id, name_esc))
        else:
            g_outfd.write("  \\node[cloud, draw=gray, text=lightgray, fill=gray!3, minimum width=9cm, minimum height=6cm, xshift=%scm, yshift=%scm] (%s) at (0,0) {\\Huge %s};\n"%(xpos, -ypos, name_id, name_esc))

def make_connect(typ, srcdev, srcint, dstdev, dstint, label, show):
    global g_outfd
    label_esc = label.replace('_', '\_')
    hidecolor=", color=black"
    if show == False:
        hidecolor=", color=hiddencolor"
        srcint=""
        dstint=""

    srcdev = srcdev.replace('(', '[')
    srcdev = srcdev.replace(')', ']')

    dstdev = dstdev.replace('(', '[')
    dstdev = dstdev.replace(')', ']')


    if typ.upper() == "SERIAL":
        g_outfd.write("  \\draw[thick%s] (%s) -- node[serial,  at start]{%s} node[serial, at end] {%s} (%s) node[speed,midway] {\LARGE %s};\n"%(hidecolor, srcdev, srcint, dstint, dstdev, label_esc));

    if typ.upper() == "ETH":
        g_outfd.write("  \\draw[thick%s] (%s) -- node[ethernet,  at start]{%s} node[ethernet, at end] {%s} (%s) node[speed,midway] {\LARGE %s};\n"%(hidecolor, srcdev, srcint, dstint, dstdev, label_esc));

    if typ.upper() == "MGMT":
        g_outfd.write("  \\draw[thick%s] (%s) -- node[mgmtether,  at start]{%s} node[mgmtether, at end] {%s} (%s) node[speed,midway] {\LARGE %s};\n"%(hidecolor, srcdev, srcint, dstint, dstdev, label_esc));

    if typ.upper() == "VLAN":
        g_outfd.write("  \\draw[thick%s] (%s) -- node[vlan,  at start]{%s} node[vlan, at end] {%s} (%s) node[speed,midway] {\LARGE %s};\n"%(hidecolor, srcdev, srcint, dstint, dstdev, label_esc));

    if typ.upper() == "VPN":
        if show == False:
            g_outfd.write("  \\draw[dashed%s] (%s) -- node[vpn,  at start]{%s} node[vpn, at end] {%s} (%s) node[speed,midway] {%s};\n"%(hidecolor, srcdev, srcint, dstint, dstdev, label_esc))
        else:
            g_outfd.write("  \\draw[dashed, color=red] (%s) -- node[vpn,  at start]{%s} node[vpn, at end] {%s} (%s) node[speed,midway] {%s};\n"%(srcdev, srcint, dstint, dstdev, label_esc))

def generator_header(data, outfile, viewtype, modify_date, orientation, xscale, yscale, hoffset):
    global g_outfd
    with codecs.open(outfile+"-"+viewtype+".json", 'w', encoding='utf-8') as f:
        f.write(json.dumps(data_vec, sort_keys=True, indent=4))
    g_outfd = open(outfile+"-"+viewtype+".tex", "w")
    g_outfd.write("\\input{../net_template}\n")
    g_outfd.write("\\begin{document}\n")
    if orientation == "fekvő":
        g_outfd.write("\\begin{landscape}\n")
    else:
        g_outfd.write("%\\begin{landscape}\n")
    g_outfd.write("\\pagestyle{empty}\n")
    g_outfd.write("\\definecolor{hiddencolor}{rgb}{0.95, 0.95, 0.95}\n") # hiddencolor
    xtmp = 1
    if xscale != None:
        xtmp = float(xscale)
    g_outfd.write("\\begin{figure}\n")
    g_outfd.write("\\hspace*{%scm}\n"%(int(100*hoffset*xtmp)/100.0))
    g_outfd.write("\\centering\n")
    if xscale != None:
        g_outfd.write("\\resizebox{%s\\textwidth}{!} {\n"%(xscale))
    elif yscale != None:
        g_outfd.write("\\resizebox{!}{%s\\textheight} {\n"%(yscale))
    else:
        g_outfd.write("\\resizebox{!}{0.9\\textheight} {\n")
    g_outfd.write("\\begin{tikzpicture}[node distance=10cm]\n")


def generator_tail(outfile, viewtype, modify_date, orientation, checkonly, genpng):
    global g_outfd
    g_outfd.write("\\end{tikzpicture}\n}\n")
    g_outfd.write("\\captionsetup{labelformat=empty}\n")
    g_outfd.write("\\caption{Nézet: \\textbf{%s}, utolsó módosítás: %s}\n"%(viewtype, modify_date))
    g_outfd.write("\\end{figure}\n")
    if orientation == "fekvő":
        g_outfd.write("\\end{landscape}\n")
    else:
        g_outfd.write("%\\end{landscape}\n")
    g_outfd.write("\end{document}\n")

    g_outfd.close()
    if checkonly == False:
        os.system("pdflatex '%s-%s.tex'"%(outfile, viewtype))
        if genpng:
            os.system("pdfcrop '%s-%s.pdf'"%(outfile, viewtype))
            os.system("pdftoppm '%s-%s-crop.pdf' | pnmtopng > '%s-%s.png'"%(outfile, viewtype, outfile, viewtype))

# ========= Load from Excel (xlsx) ===================

def xlsx_data_reader(xls_name, lapok):
    lapszam = 0
    data_vec = []
    for s in xlrd.open_workbook(xls_name).sheets():
        lapszam += 1
        if len(lapok) > 0 and lapszam not in lapok: continue
        if s.name == "Verzió": continue  # kimarad ez a lap
        # Olvassunk - s.name --> sheet neve
        data = {"sheetname": s.name, "views": [], "objs": [], "devs": []}
        try:
            if s.cell(0, 0).value == "Utolsó módosítás:":
                data["last_modify"] = { 'date': s.cell(0, 1).value, 'user': s.cell(0, 2).value }
            else:
                print ("Nincs módosítási információ a(z) \"%s\" (lap: %s, sor: 1) fül első sorában. EXIT."%(s.name, lapszam))
                sys.exit(-1)
        except:
            print ("Nincs módosítási információ a(z) \"%s\" (lap: %s, sor: 1) fül első sorában. EXIT."%(s.name, lapszam))
            sys.exit(-1)

        data["orientation"] = s.cell(0, 3).value
        if data["orientation"] != "álló" and data["orientation"] != "fekvő":
            print("%s első sor 3. oszlopa (%s) 'álló' vagy 'fekvő' érték kell legyen."%(s.name, data["orientation"]))
            sys.exit(-1)

        glob_pictscale = s.cell(0, 4).value.strip().lower().split('=')
        if len(glob_pictscale) != 2:
            print("%s első sor 4. oszlopába kell egy X=0.8 vagy Y=0.8 nagyítás paraméter."%(s.name))
            sys.exit(-1)
        data["hoffset"] = float(s.cell(0, 5).value)

        mode = None
        objlist = []
        for row in range(s.nrows):
            a_oszlop = s.cell(row, 0).value.strip()
            if len(a_oszlop) < 3 or a_oszlop[0] == '#': continue

            if a_oszlop == "Nézet neve":
                mode = "view"
                continue
            elif a_oszlop == "Objektumtípus":
                mode = "objs"
                continue
            elif a_oszlop == "Eszköz":
                mode = "devs"

            if mode == "view":
                view = {
                    "viewname" : s.cell(row, 0).value.strip(),
                    "objtypes" : [x for x in re.split(",|;| |\n", s.cell(row, 1).value) if len(x) > 1],
                    "conntypes": [x for x in re.split(",|;| |\n", s.cell(row, 2).value) if len(x) > 1],
                    "viewlabels": [x for x in re.split(",|;| |\n", s.cell(row, 3).value) if len(x) > 1],
                    "pictscale": glob_pictscale,
                    "tablelabels": [x for x in re.split(",|;| |\n", s.cell(row, 5).value) if len(x) > 1],
                    "show_inactive": True,
                }
                if len(set(view["conntypes"]).difference(conn_whitelist)) > 0:
                    print ("Conntype hiba %s (lap: %s, sor: %s). EXIT."%(set(view["conntypes"]).difference(conn_whitelist), s.name, row + 1))
                    print ("A kovetkezoket hasznald:", conn_whitelist)
                    sys.exit(-1)

                if len(s.cell(row, 4).value.strip()) > 2:
                    view["pictscale"] = s.cell(row, 4).value.strip().lower().split('=')
                    view["show_inactive"] = False
                data["views"].append(view)

            if mode == "objs":
                print(row, s.cell(row, 4).value)
                obj = {
                    "objtype" : s.cell(row, 0).value.strip(),
                    "objname" : s.cell(row, 1).value.strip(),
                    "product": s.cell(row, 2).value.strip(),
                    "mgmtip": s.cell(row, 3).value.strip(),
                    "xpos": float(s.cell(row, 4).value),
                    "ypos": float(s.cell(row, 5).value),
                    "show": False,
                }
                data["objs"].append(obj)

                if obj["objtype"] not in objtype_whitelist:
                    print ("Hiba a %s lapon a %s sorban (%s): objektumtípus a következő lehet: %s"%(s.name, row+1, obj["objtype"], str(objtype_whitelist)))
                    sys.exit(-1)

                if obj["objname"] in objlist:
                    print ("Duplikált objektum: %s (lap: %s, sor: %s). EXIT."%(obj["objname"], s.name, row + 1))
                    sys.exit(-1)
                objlist.append(obj["objname"])

            if mode == "devs" and s.cell(row, 0).value.strip() == "Eszköz":
                dev = {
                    "conntype": s.cell(row, 1).value.strip(),
                    "objname" : s.cell(row, 2).value.strip(),
                    "gw_addr" : s.cell(row, 3).value.strip(),
                    "management_ip" : s.cell(row, 4).value.strip(),
                    "peerdata" : {},
                }
                if len(dev["conntype"]) > 0 and dev["conntype"] not in conn_whitelist:
                    print ("Conntype hiba %s (lap: %s, sor: %s). EXIT."%(dev["conntype"], s.name, row + 1))
                    print ("A kovetkezoket hasznald:", conn_whitelist)
                    sys.exit(-1)

                if dev["objname"] not in objlist:
                    print ("Nem definiált objektum: %s (lap: %s, sor: %s). EXIT."%(dev["objname"], s.name, row + 1))
                    sys.exit(-1)

                hdrnames = ["Port", "Objektum neve", "Eszköz port", "Link felirat", "Eszköz IP címei", "Eszköz VRRP IP", "Nézet cimkék"]
                hdrlabel = ["switchport", "objname", "port",        "linklabel",    "ipaddrs",          "vrrp_ip",        "viewlabels"]
                for i in range(len(hdrnames)):
                    peerdata = []
                    for c in range(1, s.ncols):
                        if s.cell(row + 1 + i, 0).value.strip() == hdrnames[i]:
                            cellvalue = s.cell(row + 1 + i, c).value
                            if hdrlabel[i] == "viewlabels":
                                cellvalue = [x for x in re.split(",|;| |\n", cellvalue) if len(x) > 1]
                                peerdata.append(cellvalue)
                            else:
                                if type(cellvalue) == float:
                                    cellvalue = int(cellvalue)
                                peerdata.append(str(cellvalue).strip())
                            if i == 1 and len(peerdata[-1]) > 1 and peerdata[-1] not in objlist:
                                print ("Nem definiált objektum: %s (lap: %s, sor: %s). EXIT."%(peerdata[-1], s.name, row + 2 + i))
                                sys.exit(-1)
                        else:
                            print ("Hiányzó \"%\" sor a(z) \"%s\" (lap: %s, sor: %s) helyen. EXIT."%(hdrnames[i], s.name, lapszam, row + 2 + i))
                            sys.exit(-1)

                    dev["peerdata"][hdrlabel[i]] = peerdata
                data["devs"].append(dev)
        data_vec.append(data)
        with codecs.open("%s/debug_%s.json"%(GENDIR, s.name), 'w', encoding='utf-8') as f:
            f.write(json.dumps(data_vec, sort_keys=True, indent=4))

    return data_vec

def xlsx_view_filter(data_vec):
    filtered_vec = []
    for view in data_vec["views"]:
        filtered = copy.deepcopy(data_vec)
        for di in range(len(filtered["devs"])):
            devs = filtered["devs"][di]
            devs["peerdata"]["show"] = []
            dev_ok = False
            for pi in range(len(devs["peerdata"]["port"])):
                if len(view["conntypes"]) == 0 or devs["peerdata"]["port"][pi].rstrip("0123456789.").lower() in view["conntypes"] or len(set(devs["peerdata"]["viewlabels"][pi]).intersection(view["viewlabels"])) > 0:
                    #print ("---> {%s} ---- {%s}"%(devs["peerdata"]["port"][pi], view["conntypes"]))
                    devs["peerdata"]["show"].append(True)
                    for oi in range(len(filtered["objs"])):
                        objs = filtered["objs"][oi]
                        if objs["objname"] == devs["peerdata"]["objname"][pi]:
                            #print (view["viewname"], objs["objname"], "True") ##
                            objs["show"] = True
                            dev_ok = True
                else:
                    devs["peerdata"]["show"].append(False)
            if dev_ok == True or devs["conntype"] in view["conntypes"]:
                for oi in range(len(filtered["objs"])):
                    objs = filtered["objs"][oi]
                    if objs["objname"] == devs["objname"]:
                        objs["show"] = True

        filtered["act_view"] = view
        filtered_vec.append(filtered)
    #print(json.dumps(filtered_vec, sort_keys=True, indent=4))
    return filtered_vec

def generate_graph(data, checkonly, genpng):
    sc = data["act_view"]["pictscale"]
    xscale = None
    yscale = None
    if sc[0] == 'x':
        xscale = sc[1]
    if sc[0] == 'y':
        yscale = sc[1]

    os.chdir(GENDIR)
    generator_header(data, data["sheetname"], data["act_view"]["viewname"], data["last_modify"]["date"], data["orientation"], xscale, yscale, data["hoffset"])
    for obj in data["objs"]:
        if obj["show"] == True or data["act_view"]["show_inactive"]:
            place_node( obj["objname"], obj["objtype"], obj["mgmtip"], obj["xpos"], obj["ypos"], obj["show"])
    for dev in data["devs"]:
        peer = dev["peerdata"]
        for i in range(len(peer["switchport"])):
            if len(peer["objname"][i]) > 0 and (peer["show"][i] == True or data["act_view"]["show_inactive"]):
                make_connect(dev["conntype"], dev["objname"], peer["switchport"][i], peer["objname"][i], peer["port"][i], peer["linklabel"][i], peer["show"][i])

    generator_tail(data["sheetname"], data["act_view"]["viewname"], data["last_modify"]["date"], data["orientation"], checkonly, genpng)
    os.chdir("..")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print ("\nKell paraméternek egy xlsx hálózat leíró fájl")
        print ("   és opcionálisan felsorolva, hogy mely lapokat generálja.")
        print ("   -p ha PNG fájl is kell (mellékesen *-crop.pdf is generálva lesz)")
        print ("   -c ha nem akarunk PDF-et és PNG-t generálni, csak ellenőrizni az xlsx helyességét.")
        sys.exit(-1)
    try:
        os.mkdir(GENDIR)
    except:
        pass


    checkonly = False
    png = False
    lapok = []
    for lap in sys.argv[1:]:
        if lap == '-c':
            checkonly = True
        elif lap == '-p':
            png = True
        elif len(lap) <= 3:
            lapok.append(int(lap))
        else:
            xls_name = lap

    # felolvassuk, laponként nézetet generálunk, nézeteket lerajzoljuk
    data_vec = xlsx_data_reader(xls_name, lapok)
    for data in data_vec:
        filtered_vec = xlsx_view_filter(data)
        for data in filtered_vec:
            generate_graph(data, checkonly, png)

    if not checkonly:
        filename = xls_name.split('.')[0]+".tex"
        doksi_ossszefuzes(filename)
