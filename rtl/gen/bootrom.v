// =============================================================================
// GENERATED FILE - DO NOT EDIT.
// Source : sw/build/boot/boot.elf (sha256/16 4c71f0bd5a8ed007)
// Tool   : tools/gen_bootrom.py
// -----------------------------------------------------------------------------
// bootrom.v - boot ROM, 512 words, 330 used by the image
// Purpose : Holds the UART bootloader. Contents are a case statement, so no
//           initial block or $readmemh is needed.
// Behavior: Two independent read ports, each registered with an enable; when
//           a port is not enabled its output holds (same contract as soc_ram).
//           rom_style = "block" asks Vivado to map the ROM to block RAM.
// =============================================================================
`default_nettype none

module bootrom (
    //== Ports
    input  wire          clk,
    input  wire          a_en,
    input  wire [8:0]   a_addr,
    output wire [31:0]   a_rdata,
    input  wire          b_en,
    input  wire [8:0]   b_addr,
    output wire [31:0]   b_rdata
);

    //== Localparams/Wires
    (* rom_style = "block" *) reg [31:0] a_rdata_q;
    (* rom_style = "block" *) reg [31:0] b_rdata_q;
    reg  [31:0] a_word;
    reg  [31:0] b_word;

    function [31:0] rom_word;
        input [8:0] addr;
        begin
            case (addr)
            9'd0: rom_word = 32'h80010117;
            9'd1: rom_word = 32'h00010113;
            9'd2: rom_word = 32'h00000297;
            9'd3: rom_word = 32'h01428293;
            9'd4: rom_word = 32'h30529073;
            9'd5: rom_word = 32'h220000EF;
            9'd6: rom_word = 32'h0000006F;
            9'd7: rom_word = 32'h34202573;
            9'd8: rom_word = 32'h341025F3;
            9'd9: rom_word = 32'h34302673;
            9'd10: rom_word = 32'h80010117;
            9'd11: rom_word = 32'hFD810113;
            9'd12: rom_word = 32'h194000EF;
            9'd13: rom_word = 32'h0000006F;
            9'd14: rom_word = 32'h40000737;
            9'd15: rom_word = 32'h00870713;
            9'd16: rom_word = 32'h00072783;
            9'd17: rom_word = 32'h0017F793;
            9'd18: rom_word = 32'hFE079CE3;
            9'd19: rom_word = 32'h0FF57513;
            9'd20: rom_word = 32'h400007B7;
            9'd21: rom_word = 32'h00A7A023;
            9'd22: rom_word = 32'h00008067;
            9'd23: rom_word = 32'hFF010113;
            9'd24: rom_word = 32'h00812423;
            9'd25: rom_word = 32'h00112623;
            9'd26: rom_word = 32'h00050413;
            9'd27: rom_word = 32'h00044503;
            9'd28: rom_word = 32'h00051A63;
            9'd29: rom_word = 32'h00C12083;
            9'd30: rom_word = 32'h00812403;
            9'd31: rom_word = 32'h01010113;
            9'd32: rom_word = 32'h00008067;
            9'd33: rom_word = 32'h00140413;
            9'd34: rom_word = 32'hFB1FF0EF;
            9'd35: rom_word = 32'hFE1FF06F;
            9'd36: rom_word = 32'hFE010113;
            9'd37: rom_word = 32'h00812C23;
            9'd38: rom_word = 32'h00912A23;
            9'd39: rom_word = 32'h01212823;
            9'd40: rom_word = 32'h01312623;
            9'd41: rom_word = 32'h00112E23;
            9'd42: rom_word = 32'h00050493;
            9'd43: rom_word = 32'h01C00413;
            9'd44: rom_word = 32'h00900993;
            9'd45: rom_word = 32'hFFC00913;
            9'd46: rom_word = 32'h0084D7B3;
            9'd47: rom_word = 32'h00F7F793;
            9'd48: rom_word = 32'h05778513;
            9'd49: rom_word = 32'h00F9E463;
            9'd50: rom_word = 32'h03078513;
            9'd51: rom_word = 32'hFFC40413;
            9'd52: rom_word = 32'hF69FF0EF;
            9'd53: rom_word = 32'hFF2412E3;
            9'd54: rom_word = 32'h01C12083;
            9'd55: rom_word = 32'h01812403;
            9'd56: rom_word = 32'h01412483;
            9'd57: rom_word = 32'h01012903;
            9'd58: rom_word = 32'h00C12983;
            9'd59: rom_word = 32'h02010113;
            9'd60: rom_word = 32'h00008067;
            9'd61: rom_word = 32'h40000737;
            9'd62: rom_word = 32'h00870713;
            9'd63: rom_word = 32'h00072783;
            9'd64: rom_word = 32'h0027F793;
            9'd65: rom_word = 32'hFE078CE3;
            9'd66: rom_word = 32'h400007B7;
            9'd67: rom_word = 32'h0047A503;
            9'd68: rom_word = 32'h0FF57513;
            9'd69: rom_word = 32'h00008067;
            9'd70: rom_word = 32'hFF010113;
            9'd71: rom_word = 32'h00112623;
            9'd72: rom_word = 32'h00812423;
            9'd73: rom_word = 32'h00912223;
            9'd74: rom_word = 32'hFCDFF0EF;
            9'd75: rom_word = 32'h00050493;
            9'd76: rom_word = 32'hFC5FF0EF;
            9'd77: rom_word = 32'h00050413;
            9'd78: rom_word = 32'hFBDFF0EF;
            9'd79: rom_word = 32'h01051513;
            9'd80: rom_word = 32'h00841413;
            9'd81: rom_word = 32'h00A46433;
            9'd82: rom_word = 32'hFADFF0EF;
            9'd83: rom_word = 32'h00946433;
            9'd84: rom_word = 32'h01851513;
            9'd85: rom_word = 32'h00C12083;
            9'd86: rom_word = 32'h00856533;
            9'd87: rom_word = 32'h00812403;
            9'd88: rom_word = 32'h00412483;
            9'd89: rom_word = 32'h01010113;
            9'd90: rom_word = 32'h00008067;
            9'd91: rom_word = 32'hFF010113;
            9'd92: rom_word = 32'h00112623;
            9'd93: rom_word = 32'h00812423;
            9'd94: rom_word = 32'h00050413;
            9'd95: rom_word = 32'hEBDFF0EF;
            9'd96: rom_word = 32'h00845513;
            9'd97: rom_word = 32'hEB5FF0EF;
            9'd98: rom_word = 32'h01045513;
            9'd99: rom_word = 32'hEADFF0EF;
            9'd100: rom_word = 32'h01845513;
            9'd101: rom_word = 32'h00812403;
            9'd102: rom_word = 32'h00C12083;
            9'd103: rom_word = 32'h01010113;
            9'd104: rom_word = 32'hE99FF06F;
            9'd105: rom_word = 32'h40000737;
            9'd106: rom_word = 32'h00870713;
            9'd107: rom_word = 32'h00072783;
            9'd108: rom_word = 32'h0017F793;
            9'd109: rom_word = 32'hFE079CE3;
            9'd110: rom_word = 32'h400007B7;
            9'd111: rom_word = 32'h1007A023;
            9'd112: rom_word = 32'h00050067;
            9'd113: rom_word = 32'hFF010113;
            9'd114: rom_word = 32'h00812423;
            9'd115: rom_word = 32'h00050413;
            9'd116: rom_word = 32'h49800513;
            9'd117: rom_word = 32'h00112623;
            9'd118: rom_word = 32'h00912223;
            9'd119: rom_word = 32'h01212023;
            9'd120: rom_word = 32'h00060493;
            9'd121: rom_word = 32'h00058913;
            9'd122: rom_word = 32'hE75FF0EF;
            9'd123: rom_word = 32'h00040513;
            9'd124: rom_word = 32'hEA1FF0EF;
            9'd125: rom_word = 32'h4AC00513;
            9'd126: rom_word = 32'hE65FF0EF;
            9'd127: rom_word = 32'h00090513;
            9'd128: rom_word = 32'hE91FF0EF;
            9'd129: rom_word = 32'h4B400513;
            9'd130: rom_word = 32'hE55FF0EF;
            9'd131: rom_word = 32'h00048513;
            9'd132: rom_word = 32'hE81FF0EF;
            9'd133: rom_word = 32'h52000513;
            9'd134: rom_word = 32'hE45FF0EF;
            9'd135: rom_word = 32'hEEEE07B7;
            9'd136: rom_word = 32'h0FF47413;
            9'd137: rom_word = 32'h00F46433;
            9'd138: rom_word = 32'h400007B7;
            9'd139: rom_word = 32'h2087A023;
            9'd140: rom_word = 32'h0000006F;
            9'd141: rom_word = 32'hFD010113;
            9'd142: rom_word = 32'hB00707B7;
            9'd143: rom_word = 32'h40000737;
            9'd144: rom_word = 32'h02112623;
            9'd145: rom_word = 32'h02812423;
            9'd146: rom_word = 32'h02912223;
            9'd147: rom_word = 32'h03212023;
            9'd148: rom_word = 32'h01312E23;
            9'd149: rom_word = 32'h01412C23;
            9'd150: rom_word = 32'h01512A23;
            9'd151: rom_word = 32'h01612823;
            9'd152: rom_word = 32'h01712623;
            9'd153: rom_word = 32'h01812423;
            9'd154: rom_word = 32'h01912223;
            9'd155: rom_word = 32'h01A12023;
            9'd156: rom_word = 32'h00178793;
            9'd157: rom_word = 32'h20F72023;
            9'd158: rom_word = 32'h00070793;
            9'd159: rom_word = 32'h00008737;
            9'd160: rom_word = 32'h10E7A023;
            9'd161: rom_word = 32'h1047A783;
            9'd162: rom_word = 32'h01079713;
            9'd163: rom_word = 32'h00075A63;
            9'd164: rom_word = 32'h4BC00513;
            9'd165: rom_word = 32'hDC9FF0EF;
            9'd166: rom_word = 32'h80000537;
            9'd167: rom_word = 32'hF09FF0EF;
            9'd168: rom_word = 32'h4EC00513;
            9'd169: rom_word = 32'hDB9FF0EF;
            9'd170: rom_word = 32'h80000537;
            9'd171: rom_word = 32'hDE5FF0EF;
            9'd172: rom_word = 32'h50800513;
            9'd173: rom_word = 32'hDA9FF0EF;
            9'd174: rom_word = 32'h00010537;
            9'd175: rom_word = 32'hDD5FF0EF;
            9'd176: rom_word = 32'h50C00513;
            9'd177: rom_word = 32'h00010A37;
            9'd178: rom_word = 32'hEDB889B7;
            9'd179: rom_word = 32'hD91FF0EF;
            9'd180: rom_word = 32'h00000913;
            9'd181: rom_word = 32'h05000B13;
            9'd182: rom_word = 32'h05700A93;
            9'd183: rom_word = 32'h80000BB7;
            9'd184: rom_word = 32'hF00A0A13;
            9'd185: rom_word = 32'h32098993;
            9'd186: rom_word = 32'hE0DFF0EF;
            9'd187: rom_word = 32'h00050413;
            9'd188: rom_word = 32'h03651E63;
            9'd189: rom_word = 32'h04B00513;
            9'd190: rom_word = 32'hD41FF0EF;
            9'd191: rom_word = 32'h52400513;
            9'd192: rom_word = 32'hD5DFF0EF;
            9'd193: rom_word = 32'h00100513;
            9'd194: rom_word = 32'hD31FF0EF;
            9'd195: rom_word = 32'h80000537;
            9'd196: rom_word = 32'hE5DFF0EF;
            9'd197: rom_word = 32'h00010537;
            9'd198: rom_word = 32'hE55FF0EF;
            9'd199: rom_word = 32'h80010537;
            9'd200: rom_word = 32'hF0050513;
            9'd201: rom_word = 32'hE49FF0EF;
            9'd202: rom_word = 32'hFC1FF06F;
            9'd203: rom_word = 32'h01550663;
            9'd204: rom_word = 32'h05200793;
            9'd205: rom_word = 32'h12F51863;
            9'd206: rom_word = 32'hDE1FF0EF;
            9'd207: rom_word = 32'h00050493;
            9'd208: rom_word = 32'hDD9FF0EF;
            9'd209: rom_word = 32'h017487B3;
            9'd210: rom_word = 32'h00050C13;
            9'd211: rom_word = 32'h02FA6A63;
            9'd212: rom_word = 32'h800107B7;
            9'd213: rom_word = 32'hF0078793;
            9'd214: rom_word = 32'h409787B3;
            9'd215: rom_word = 32'h02A7E263;
            9'd216: rom_word = 32'h04B00513;
            9'd217: rom_word = 32'hCD5FF0EF;
            9'd218: rom_word = 32'h00000C93;
            9'd219: rom_word = 32'h09540063;
            9'd220: rom_word = 32'hFFF00413;
            9'd221: rom_word = 32'h0B8C9A63;
            9'd222: rom_word = 32'hFFF44513;
            9'd223: rom_word = 32'hFA9FF06F;
            9'd224: rom_word = 32'h04500513;
            9'd225: rom_word = 32'hCB5FF0EF;
            9'd226: rom_word = 32'h07200513;
            9'd227: rom_word = 32'hCADFF0EF;
            9'd228: rom_word = 32'hF59FF06F;
            9'd229: rom_word = 32'hD61FF0EF;
            9'd230: rom_word = 32'h009C87B3;
            9'd231: rom_word = 32'h00A78023;
            9'd232: rom_word = 32'h00A44433;
            9'd233: rom_word = 32'h00800793;
            9'd234: rom_word = 32'h00145713;
            9'd235: rom_word = 32'h00147413;
            9'd236: rom_word = 32'h40800433;
            9'd237: rom_word = 32'h01347433;
            9'd238: rom_word = 32'hFFF78793;
            9'd239: rom_word = 32'h00874433;
            9'd240: rom_word = 32'hFE0794E3;
            9'd241: rom_word = 32'h001C8C93;
            9'd242: rom_word = 32'hFD8C96E3;
            9'd243: rom_word = 32'hD4DFF0EF;
            9'd244: rom_word = 32'hFFF44413;
            9'd245: rom_word = 32'h00050493;
            9'd246: rom_word = 32'h00850E63;
            9'd247: rom_word = 32'h04500513;
            9'd248: rom_word = 32'hC59FF0EF;
            9'd249: rom_word = 32'h06300513;
            9'd250: rom_word = 32'hFA5FF06F;
            9'd251: rom_word = 32'hFFF00413;
            9'd252: rom_word = 32'hFD9FF06F;
            9'd253: rom_word = 32'h04B00513;
            9'd254: rom_word = 32'hC41FF0EF;
            9'd255: rom_word = 32'h00048513;
            9'd256: rom_word = 32'hD6DFF0EF;
            9'd257: rom_word = 32'h01990933;
            9'd258: rom_word = 32'h400007B7;
            9'd259: rom_word = 32'h2127A023;
            9'd260: rom_word = 32'h00008737;
            9'd261: rom_word = 32'h00A95793;
            9'd262: rom_word = 32'h00E7E7B3;
            9'd263: rom_word = 32'h40000737;
            9'd264: rom_word = 32'h10F72023;
            9'd265: rom_word = 32'hEC5FF06F;
            9'd266: rom_word = 32'h009C8D33;
            9'd267: rom_word = 32'h000D4503;
            9'd268: rom_word = 32'hC09FF0EF;
            9'd269: rom_word = 32'h000D4783;
            9'd270: rom_word = 32'h00F44433;
            9'd271: rom_word = 32'h00800793;
            9'd272: rom_word = 32'h00145713;
            9'd273: rom_word = 32'h00147413;
            9'd274: rom_word = 32'h40800433;
            9'd275: rom_word = 32'h01347433;
            9'd276: rom_word = 32'hFFF78793;
            9'd277: rom_word = 32'h00874433;
            9'd278: rom_word = 32'hFE0794E3;
            9'd279: rom_word = 32'h001C8C93;
            9'd280: rom_word = 32'hF15FF06F;
            9'd281: rom_word = 32'h04700793;
            9'd282: rom_word = 32'h02F51063;
            9'd283: rom_word = 32'hCADFF0EF;
            9'd284: rom_word = 32'h00050413;
            9'd285: rom_word = 32'h04B00513;
            9'd286: rom_word = 32'hBC1FF0EF;
            9'd287: rom_word = 32'h00040513;
            9'd288: rom_word = 32'hD25FF0EF;
            9'd289: rom_word = 32'hE65FF06F;
            9'd290: rom_word = 32'h04500513;
            9'd291: rom_word = 32'hBADFF0EF;
            9'd292: rom_word = 32'h03F00513;
            9'd293: rom_word = 32'hEF9FF06F;
            9'd294: rom_word = 32'h4F420A0D;
            9'd295: rom_word = 32'h5420544F;
            9'd296: rom_word = 32'h20504152;
            9'd297: rom_word = 32'h7561636D;
            9'd298: rom_word = 32'h003D6573;
            9'd299: rom_word = 32'h70656D20;
            9'd300: rom_word = 32'h00003D63;
            9'd301: rom_word = 32'h76746D20;
            9'd302: rom_word = 32'h003D6C61;
            9'd303: rom_word = 32'h656E0A0D;
            9'd304: rom_word = 32'h5F737978;
            9'd305: rom_word = 32'h32337672;
            9'd306: rom_word = 32'h6F6F6220;
            9'd307: rom_word = 32'h53203A74;
            9'd308: rom_word = 32'h20353157;
            9'd309: rom_word = 32'h202C7075;
            9'd310: rom_word = 32'h6E6E7572;
            9'd311: rom_word = 32'h20676E69;
            9'd312: rom_word = 32'h204D4152;
            9'd313: rom_word = 32'h67616D69;
            9'd314: rom_word = 32'h000A0D65;
            9'd315: rom_word = 32'h656E0A0D;
            9'd316: rom_word = 32'h5F737978;
            9'd317: rom_word = 32'h32337672;
            9'd318: rom_word = 32'h6F6F6220;
            9'd319: rom_word = 32'h31762074;
            9'd320: rom_word = 32'h4152202C;
            9'd321: rom_word = 32'h0000204D;
            9'd322: rom_word = 32'h0000002B;
            9'd323: rom_word = 32'h6177202C;
            9'd324: rom_word = 32'h6E697469;
            9'd325: rom_word = 32'h6F662067;
            9'd326: rom_word = 32'h76722072;
            9'd327: rom_word = 32'h64616F6C;
            9'd328: rom_word = 32'h00000A0D;
            9'd329: rom_word = 32'h4C425652;
            default: rom_word = 32'h00000000;
            endcase
        end
    endfunction

    //== Combinational Logic
    always @(*) begin
        a_word = rom_word(a_addr);
        b_word = rom_word(b_addr);
    end

    assign a_rdata = a_rdata_q;
    assign b_rdata = b_rdata_q;

    //== Sequential Logic
    always @(posedge clk) begin
        if (a_en) begin
            a_rdata_q <= a_word;
        end
        if (b_en) begin
            b_rdata_q <= b_word;
        end
    end

endmodule

`default_nettype wire
